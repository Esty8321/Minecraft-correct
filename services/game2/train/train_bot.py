# services/game2/train/train_bot.py
from __future__ import annotations
import json, os
from collections import defaultdict
from typing import Dict, List, Tuple
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader
import torch.nn as nn
import torch.optim as optim

from services.game2.models.bot_gru import GRUPolicy, NUM_ACTIONS
from services.game2.core.settings import HISTORY_JSON_PATH, W, H

HIST_JSONL = Path(str(HISTORY_JSON_PATH).replace(".json", ".jsonl"))  # .../history.jsonl

# ---------- קריאת לוגים ----------
def load_sessions() -> Dict[Tuple[str,str], List[dict]]:
    sessions = defaultdict(list)  # key=(player_id,chunk_id) -> list of {ts, token, board}
    with open(HIST_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            # מבנה לפי db_history.append_player_action
            # fields: player_id, chunk_id, token(int), board(string of flat ints), ts(string)
            rec["token"] = int(rec["token"])
            rec["board"] = torch.tensor(json.loads(rec["board"]), dtype=torch.uint8).view(H, W)
            sessions[(rec["player_id"], rec["chunk_id"])].append(rec)
    # למיין בזמן (אם צריך)
    for k in sessions:
        sessions[k].sort(key=lambda r: r["ts"])
    return sessions

# ---------- בניית ווקאב למשתמשים ----------
def build_user_vocab(sessions: Dict[Tuple[str,str], List[dict]]) -> Dict[str,int]:
    users = sorted({pid for (pid, _) in sessions.keys()})
    return {u:i for i,u in enumerate(users)}

# ---------- דסאט ----------
class NextActionDataset(Dataset):
    def __init__(self, sessions: Dict[Tuple[str,str], List[dict]], user_vocab: Dict[str,int]):
        self.samples = []
        for (pid, cid), seq in sessions.items():
            if len(seq) < 2:
                continue
            for t in range(len(seq)-1):
                cur = seq[t]
                nxt = seq[t+1]
                self.samples.append({
                    "user_id": pid,
                    "board": cur["board"],         # מצב לוח בזמן t
                    "prev_token": cur["token"],    # פעולה שבוצעה ב-t
                    "target": nxt["token"] - 1,    # לפלט קטגוריאלי [0..5]
                })
        self.user_vocab = user_vocab

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        board = s["board"].unsqueeze(0)  # (1,H,W)
        prev_t = s["prev_token"]
        target = s["target"]
        uidx = self.user_vocab[s["user_id"]]
        return board, prev_t, uidx, target

# ---------- אימון ----------
def train(epochs=5, batch_size=64, lr=1e-3, device="cpu", out_path="bot_gru.pt"):
    sessions = load_sessions()
    user_vocab = build_user_vocab(sessions)
    ds = NextActionDataset(sessions, user_vocab)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)

    model = GRUPolicy(num_users=len(user_vocab)).to(device)
    opt = optim.Adam(model.parameters(), lr=lr)
    crit = nn.CrossEntropyLoss()

    for ep in range(1, epochs+1):
        model.train()
        total, correct, loss_sum = 0, 0, 0.0
        for board, prev_token, uidx, target in dl:
            board = board.to(device).float().unsqueeze(1)  # (B,1,H,W)
            prev_token = prev_token.to(device)
            uidx = uidx.to(device)
            target = target.to(device)

            # GRU צעד בודד — נשתמש h0=0
            logits_list = []
            h = None
            for i in range(board.size(0)):  # פולד-לופ מיני—שומר פשטות
                logits, h = model.forward_step(board[i:i+1], int(prev_token[i]), int(uidx[i]), h=None)
                logits_list.append(logits)
            logits = torch.cat(logits_list, dim=0)  # (B,NUM_ACTIONS)

            loss = crit(logits, target)
            opt.zero_grad()
            loss.backward()
            opt.step()

            loss_sum += loss.item() * board.size(0)
            total += board.size(0)
            pred = logits.argmax(dim=1)
            correct += (pred == target).sum().item()

        print(f"[ep {ep}] loss={loss_sum/total:.4f} acc={correct/total:.3f}")

    torch.save({
        "state_dict": model.state_dict(),
        "user_vocab": user_vocab,
    }, out_path)
    print(f"Saved weights to {out_path}")

if __name__ == "__main__":
    # דוגמה: python -m services.game2.train.train_bot -- ירוץ ברירת מחדל
    train()
