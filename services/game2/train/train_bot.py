# services/game2/train/train_bot.py
from __future__ import annotations
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Any
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader
import torch.nn as nn
import torch.optim as optim

from services.game2.models.bot_gru import GRUPolicy, NUM_ACTIONS
from services.game2.core.settings import HISTORY_JSON_PATH, W, H

# ---------------------------------------------------------
# איתור קובץ ההיסטוריה: ננסה כמה מועמדים סבירים
# ---------------------------------------------------------
def _find_history_file() -> Path:
    candidates = [
        Path("data/actions.jsonl"),
        Path("data/history.jsonl"),
        Path(str(HISTORY_JSON_PATH).replace(".json", ".jsonl")),
        Path(HISTORY_JSON_PATH),
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Could not find any history file. Tried: "
        + ", ".join(str(p) for p in candidates)
    )

# ---------------------------------------------------------
# טעינת לוח מ-snapshot (.pt)
# תומך בכמה מבנים נפוצים: טנסור ישיר, או dict עם board/matrix/data/grid,
# או dict עם state שמכיל אחד מהמפתחות הללו.
# ---------------------------------------------------------
def _load_board_from_snapshot(path_str: str) -> torch.Tensor:
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"snapshot not found: {p}")

    obj: Any = torch.load(p, map_location="cpu")

    def _as_board(t: Any) -> torch.Tensor:
        t = torch.as_tensor(t)
        # אם קיבלנו (1,H,W) — נסיר מימד באצ' אם צריך
        if t.ndim == 3 and t.shape[0] == 1:
            t = t[0]
        # אם קיבלנו (H*W,) — נעצב ל-(H,W)
        if t.ndim == 1 and t.numel() == H * W:
            t = t.view(H, W)
        if t.ndim != 2 or t.shape != (H, W):
            raise ValueError(f"Unexpected board shape {tuple(t.shape)}, expected {(H, W)}")
        return t.to(torch.uint8)

    # 1) טנסור ישיר
    if isinstance(obj, torch.Tensor):
        return _as_board(obj)

    # 2) מילון עם מפתחות אפשריים
    if isinstance(obj, dict):
        for key in ("board", "matrix", "data", "grid"):
            if key in obj:
                return _as_board(obj[key])
        # 3) ייתכן תחת 'state'
        if "state" in obj and isinstance(obj["state"], dict):
            st = obj["state"]
            for key in ("board", "matrix", "data", "grid"):
                if key in st:
                    return _as_board(st[key])

    raise KeyError(f"Could not find board in snapshot: {p}")

# ---------------------------------------------------------
# קריאת לוגים ל-(player_id, chunk_id) → רצף רשומות
# תומך גם ברשומות עם 'board' וגם ברשומות עם 'snapshot_path'
# + בונה מפה של תפוסה (players אחרים) לכל רשומה
# ---------------------------------------------------------
def load_sessions() -> Dict[Tuple[str, str], List[dict]]:
    src = _find_history_file()
    sessions: Dict[Tuple[str, str], List[dict]] = defaultdict(list)

    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)

            # שדות בסיסיים
            pid = rec.get("player_id")
            cid = rec.get("chunk_id")
            tok = int(rec.get("token"))

            # הטענת לוח: או משדה 'board' (רשימת ints שטוחה), או מתוך snapshot_path
            if "board" in rec:
                board = torch.tensor(json.loads(rec["board"]), dtype=torch.uint8).view(H, W)
            elif "snapshot_path" in rec:
                board = _load_board_from_snapshot(rec["snapshot_path"])
            else:
                # אין יכולת לשחזר מצב — מדלגים
                continue

            # בניית מפת תפוסה של שחקנים אחרים
            occ = torch.zeros((H, W), dtype=torch.uint8)
            players = rec.get("players", []) or []
            me = pid
            for p in players:
                try:
                    other_id = p.get("id")
                    r = int(p.get("row", -1))
                    c = int(p.get("col", -1))
                    if other_id and other_id != me and 0 <= r < H and 0 <= c < W:
                        occ[r, c] = 255  # נשתמש בערך 255 כדי שסקיילינג /255.0 ייתן 1.0
                except Exception:
                    # נתונים חלקיים—נתעלם
                    pass

            sessions[(pid, cid)].append({
                "ts": rec.get("ts", ""),
                "player_id": pid,
                "chunk_id": cid,
                "token": tok,
                "board": board,  # (H, W) uint8
                "occ": occ,      # (H, W) uint8
            })

    # מיון כרונולוגי (בהנחה שה-ts לקסיקוגרפי עולה)
    for k in sessions:
        sessions[k].sort(key=lambda r: r["ts"])
    return sessions

# ---------------------------------------------------------
# בניית ווקאב למשתמשים
# ---------------------------------------------------------
def build_user_vocab(sessions: Dict[Tuple[str, str], List[dict]]) -> Dict[str, int]:
    users = sorted({pid for (pid, _) in sessions.keys()})
    return {u: i for i, u in enumerate(users)}

# ---------------------------------------------------------
# Dataset: דוגמאות של (board_t, occ_t, prev_token_t) → target = token_{t+1}-1
# ---------------------------------------------------------
class NextActionDataset(Dataset):
    def __init__(self, sessions: Dict[Tuple[str, str], List[dict]], user_vocab: Dict[str, int]):
        self.samples = []
        for (pid, cid), seq in sessions.items():
            if len(seq) < 2:
                continue
            for t in range(len(seq) - 1):
                cur = seq[t]
                nxt = seq[t + 1]
                self.samples.append({
                    "user_id": pid,
                    "board": cur["board"],        # (H, W)
                    "occ":   cur["occ"],          # (H, W)
                    "prev_token": cur["token"],   # int
                    "target": int(nxt["token"]) - 1,  # 0..(NUM_ACTIONS-1)
                })
        self.user_vocab = user_vocab

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        # נחזיר (1,H,W) לכל ערוץ כדי שה-DataLoader יחזיר (B,1,H,W)
        board = s["board"].unsqueeze(0)                 # (1, H, W) uint8
        occ   = s["occ"].unsqueeze(0)                   # (1, H, W) uint8
        prev_t = int(s["prev_token"])                   # int
        target = int(s["target"])                       # int
        uidx = self.user_vocab[s["user_id"]]            # int
        return board, occ, prev_t, uidx, target

# ---------------------------------------------------------
# אימון
# ---------------------------------------------------------
def train(epochs: int = 20, batch_size: int = 64, lr: float = 1e-3,
          device: str = None, out_path: str = "bot_gru.pt"):

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    sessions = load_sessions()
    if not sessions:
        raise RuntimeError("No training sessions found. Make sure your history/actions file is populated.")

    user_vocab = build_user_vocab(sessions)
    if not user_vocab:
        raise RuntimeError("User vocabulary is empty. Check that your history contains player_id values.")

    ds = NextActionDataset(sessions, user_vocab)
    if len(ds) == 0:
        raise RuntimeError("Dataset is empty (need sequences of length >= 2).")

    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)

    model = GRUPolicy(num_users=len(user_vocab)).to(device)
    opt = optim.Adam(model.parameters(), lr=lr)
    crit = nn.CrossEntropyLoss()

    for ep in range(1, epochs + 1):
        model.train()
        total, correct, loss_sum = 0, 0, 0.0

        for board, occ, prev_token, uidx, target in dl:
            # board, occ: (B,1,H,W) uint8  -> float/255.0
            board = board.to(device).float() / 255.0
            occ   = occ.to(device).float()   / 255.0

            # מרכיבים 2-ערוצים: [board, occ]
            x_2ch = torch.cat([board, occ], dim=1)      # (B,2,H,W)

            prev_token = prev_token.to(device)
            uidx = uidx.to(device)
            target = target.to(device)

            # צעד עצמאי לכל אלמנט במיני-באצ' (שומר h=None לכל דוגמה)
            logits_list = []
            B = x_2ch.size(0)
            for i in range(B):
                # (1,2,H,W)
                xi = x_2ch[i:i+1]
                logits, _h = model.forward_step(xi, int(prev_token[i]), int(uidx[i]), h=None)
                logits_list.append(logits)
            logits = torch.cat(logits_list, dim=0)  # (B, NUM_ACTIONS)

            loss = crit(logits, target)
            opt.zero_grad()
            loss.backward()
            opt.step()

            loss_sum += loss.item() * B
            total += B
            pred = logits.argmax(dim=1)
            correct += (pred == target).sum().item()

        print(f"[ep {ep}] loss={loss_sum/total:.4f} acc={correct/total:.3f}")

    torch.save({
        "state_dict": model.state_dict(),
        "user_vocab": user_vocab,
    }, out_path)
    print(f"Saved weights to {out_path}")

# ---------------------------------------------------------
if __name__ == "__main__":
    # דוגמה:  py -m services.game2.train.train_bot
    train()
