from __future__ import annotations
import json, re
from collections import defaultdict
from typing import Dict, List, Tuple, Any
from pathlib import Path
from datetime import datetime
import torch
from torch.utils.data import Dataset, DataLoader, random_split
import torch.nn as nn
import torch.optim as optim
import csv
import matplotlib.pyplot as plt
from ..models.bot_gru import GRUPolicy, NUM_ACTIONS
from ..core.settings import HISTORY_JSON_PATH, W, H

SLEEP_TOKEN = 7
SLEEP_IDX = SLEEP_TOKEN - 1
MAX_GAP_SEC = 30.0

def _find_history_file() -> Path:
    candidates = [Path("data/actions.jsonl")]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Could not find any history file.")

def _load_board_from_snapshot(path_str: str) -> torch.Tensor:
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"snapshot not found: {p}")
    obj: Any = torch.load(p, map_location="cpu")
    def _as_board(t: Any) -> torch.Tensor:
        t = torch.as_tensor(t)
        if t.ndim == 3 and t.shape[0] == 1:
            t = t[0]
        if t.ndim == 1 and t.numel() == H * W:
            t = t.view(H, W)
        if t.ndim != 2 or tuple(t.shape) != (H, W):
            raise ValueError(f"Unexpected board shape {tuple(t.shape)}")
        return t.to(torch.uint8)
    if isinstance(obj, torch.Tensor):
        return _as_board(obj)
    raise KeyError(f"Could not find board in snapshot: {p}")

JSON_OBJ_REGEX = re.compile(r'\{.*?\}(?=\s*\{|\s*$)', re.S)
def _iter_json_objects_from_line(line: str):
    s = line.lstrip('\ufeff').strip()
    if not s:
        return
    matches = list(JSON_OBJ_REGEX.finditer(s))
    if matches:
        for m in matches:
            chunk = m.group(0).strip()
            try:
                yield json.loads(chunk)
            except Exception:
                continue
    else:
        try:
            yield json.loads(s)
        except Exception:
            i, j = s.find('{'), s.rfind('}')
            if i != -1 and j != -1 and j > i:
                frag = s[i:j+1]
                try:
                    yield json.loads(frag)
                except Exception:
                    return

def _build_occ_from_players(players: list, me: str | None) -> torch.Tensor:
    occ = torch.zeros((H, W), dtype=torch.uint8)
    if not isinstance(players, list):
        return occ
    for p in players:
        try:
            pid = p.get("id")
            r = int(p.get("row", -1))
            c = int(p.get("col", -1))
            if pid and pid != me and 0 <= r < H and 0 <= c < W:
                occ[r, c] = 255
        except Exception:
            continue
    return occ

def _parse_ts(ts: str) -> datetime:
    parts = ts.split('_')
    if len(parts) >= 3:
        date_s, time_s, ms_s = parts[0], parts[1], parts[2]
        dt = datetime.strptime(f"{date_s} {time_s.replace('-',':')}", "%Y-%m-%d %H:%M:%S")
        try:
            ms_i = int(ms_s)
        except Exception:
            ms_i = 0
        return dt.replace(microsecond=ms_i * 1000)
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.utcnow()

def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))

def load_sessions() -> Dict[Tuple[str, str], List[dict]]:
    src = _find_history_file()
    sessions: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    with open(src, "r", encoding="utf-8") as f:
        for raw in f:
            for rec in _iter_json_objects_from_line(raw):
                pid = rec.get("player_id")
                cid = rec.get("chunk_id")
                if pid is None or cid is None:
                    continue
                tok = int(rec.get("token"))
                if "board" in rec:
                    board = torch.tensor(json.loads(rec["board"]), dtype=torch.uint8).view(H, W)
                elif "snapshot_path" in rec:
                    board = _load_board_from_snapshot(rec["snapshot_path"])
                else:
                    continue
                players = rec.get("players", [])
                sessions[(pid, cid)].append({
                    "ts": rec.get("ts", ""),
                    "player_id": pid,
                    "chunk_id": cid,
                    "token": tok,
                    "board": board,
                    "players": players,
                })
    for k in sessions:
        sessions[k].sort(key=lambda r: r["ts"])
    return sessions

def build_user_vocab(sessions: Dict[Tuple[str, str], List[dict]]) -> Dict[str, int]:
    users = sorted({pid for (pid, _) in sessions.keys()})
    return {u: i for i, u in enumerate(users)}

class NextActionDataset(Dataset):
    def __init__(self, sessions: Dict[Tuple[str, str], List[dict]], user_vocab: Dict[str, int]):
        self.samples = []
        for (pid, cid), seq in sessions.items():
            if len(seq) < 2:
                continue
            ts_list = [_parse_ts(x.get("ts", "")) for x in seq]
            prev_deltas = [0.0] + [(ts_list[i] - ts_list[i - 1]).total_seconds() for i in range(1, len(seq))]
            next_deltas = [(ts_list[i + 1] - ts_list[i]).total_seconds() for i in range(len(seq) - 1)]
            for t in range(len(seq) - 1):
                cur = seq[t]
                nxt = seq[t + 1]
                board = cur["board"]
                occ = _build_occ_from_players(cur.get("players", []), pid)
                prev_token = int(cur["token"])
                target_tok = int(nxt["token"])
                target_idx = target_tok - 1
                prev_delta_norm = _clip01(prev_deltas[t] / MAX_GAP_SEC)
                next_delta_norm = _clip01(next_deltas[t] / MAX_GAP_SEC)
                self.samples.append({
                    "user_id": pid,
                    "board": board,
                    "occ": occ,
                    "prev_token": prev_token,
                    "prev_delta_norm": prev_delta_norm,
                    "target_idx": target_idx,
                    "sleep_delta_norm": next_delta_norm,
                })
                if next_deltas[t] > 5.0:
                    sleep_gap_norm = _clip01(next_deltas[t] / MAX_GAP_SEC)
                    self.samples.append({
                        "user_id": pid,
                        "board": board,
                        "occ": occ,
                        "prev_token": prev_token,
                        "prev_delta_norm": prev_delta_norm,
                        "target_idx": SLEEP_IDX,
                        "sleep_delta_norm": sleep_gap_norm,
                    })
        self.user_vocab = user_vocab

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        board = s["board"].unsqueeze(0)
        occ = s["occ"].unsqueeze(0)
        board2ch = torch.cat([board, occ], dim=0)
        uidx = self.user_vocab[s["user_id"]]
        return (
            board2ch,
            int(s["prev_token"]),
            int(uidx),
            int(s["target_idx"]),
            float(s["prev_delta_norm"]),
            float(s["sleep_delta_norm"]),
        )

def _split_dataset(ds: Dataset, val_ratio: float = 0.2, seed: int = 42):
    n_total = len(ds)
    n_val = int(round(n_total * val_ratio))
    n_train = n_total - n_val
    gen = torch.Generator().manual_seed(seed)
    return random_split(ds, [n_train, n_val], generator=gen)

def train(
    epochs: int = 10,
    batch_size: int = 64,
    lr: float = 1e-3,
    device: str | None = None,
    out_path: str = "bot_gru.pt",
    val_ratio: float = 0.2,
    metrics_csv: str = "training_metrics.csv",
):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    sessions = load_sessions()
    if not sessions:
        raise RuntimeError("No training sessions found.")
    user_vocab = build_user_vocab(sessions)
    ds = NextActionDataset(sessions, user_vocab)
    train_ds, val_ds = _split_dataset(ds, val_ratio, 42)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size)
    model = GRUPolicy(num_users=len(user_vocab)).to(device)
    opt = optim.Adam(model.parameters(), lr=lr)
    from collections import Counter
    counts = Counter(s['target_idx'] for s in ds.samples)
    total = sum(counts.values())
    weights = torch.tensor([total / counts.get(i, 1) for i in range(NUM_ACTIONS)],
                           dtype=torch.float32, device=device)
    ce = nn.CrossEntropyLoss(weight=weights)
    mse = nn.MSELoss()
    LAMBDA_SLEEP = 0.3
    def _batch_to_device(batch):
        board2ch, prev_token, uidx, target_idx, prev_delta_norm, sleep_delta_norm = batch
        x = board2ch.to(device)
        pt = torch.as_tensor(prev_token, dtype=torch.long, device=device)
        ui = torch.as_tensor(uidx, dtype=torch.long, device=device)
        ty = torch.as_tensor(target_idx, dtype=torch.long, device=device)
        pd = torch.as_tensor(prev_delta_norm, dtype=torch.float32, device=device)
        sd = torch.as_tensor(sleep_delta_norm, dtype=torch.float32, device=device)
        return x, pt, ui, ty, pd, sd
    def _run_epoch(dl, train_mode: bool):
        model.train() if train_mode else model.eval()
        total, correct, loss_sum = 0, 0, 0.0
        for batch in dl:
            x, pt, ui, ty, pd, sd = _batch_to_device(batch)
            if train_mode:
                opt.zero_grad()
            logits, _h, sleep_reg = model.forward_step_batch(x, pt, ui, pd)
            ce_loss = ce(logits, ty)
            sleep_mask = (ty == SLEEP_IDX).float().unsqueeze(1)
            if sleep_mask.sum() > 0:
                mse_loss = mse(sleep_reg * sleep_mask, sd.unsqueeze(1) * sleep_mask)
            else:
                mse_loss = torch.tensor(0., device=device)
            loss = ce_loss + LAMBDA_SLEEP * mse_loss
            if train_mode:
                loss.backward()
                opt.step()
            loss_sum += loss.item() * x.size(0)
            total += x.size(0)
            pred = logits.argmax(dim=1)
            correct += (pred == ty).sum().item()
        return loss_sum / max(1, total), correct / max(1, total)
    for ep in range(1, epochs + 1):
        tr_loss, tr_acc = _run_epoch(train_dl, True)
        va_loss, va_acc = _run_epoch(val_dl, False)
        print(f"[ep {ep}] train: loss={tr_loss:.4f} acc={tr_acc:.3f} | val: loss={va_loss:.4f} acc={va_acc:.3f}")
    torch.save({"state_dict": model.state_dict(), "user_vocab": user_vocab}, out_path)
    print(f"Saved weights to {out_path}")

if __name__ == "__main__":
    train()
