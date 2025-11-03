from __future__ import annotations
import torch
import torch.nn as nn
from typing import Dict, Optional, Tuple

NUM_ACTIONS = 6
HIDDEN_DIM = 128
USER_EMB_DIM = 32
BOARD_FEAT_DIM = 128
ACTION_BITS = 8
INPUT_DIM = BOARD_FEAT_DIM + ACTION_BITS + USER_EMB_DIM  # 168

def int_to_8bits(a: int, device=None) -> torch.Tensor:
    bits = [(a >> i) & 1 for i in range(8)]
    t = torch.tensor(bits, dtype=torch.float32, device=device).unsqueeze(0)  # (1,8)
    return t

class SmallBoardCNN(nn.Module):
    def __init__(self, out_dim=BOARD_FEAT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(2, 16, 3, padding=1),  # CHANGED: in_channels=2 (board+occ)
            nn.ReLU(),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),  # 32x32
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),  # 16x16
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((1,1)),     # (B,128,1,1)
        )
        self.proj = nn.Linear(128, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B,2,H,W)  ==> ערוץ 0: הלוח, ערוץ 1: מפת תפוסה (0/1)
        # עדיף לנרמל ל- [0..1]
        if x.dtype != torch.float32:
            x = x.float() / 255.0
        h = self.net(x).flatten(1)          # (B,128)
        return self.proj(h)                 # (B,BOARD_FEAT_DIM)

class GRUPolicy(nn.Module):
    def __init__(self, num_users: int):
        super().__init__()
        self.user_emb = nn.Embedding(num_users, USER_EMB_DIM)
        self.cnn = SmallBoardCNN(BOARD_FEAT_DIM)  # CHANGED: now expects 2 channels
        self.gru = nn.GRU(INPUT_DIM, HIDDEN_DIM, batch_first=True)
        self.head = nn.Linear(HIDDEN_DIM, NUM_ACTIONS)

    def forward_step(
        self,
        board_2ch: torch.Tensor,     # CHANGED: expect (1,2,H,W)
        action_token: int,           # last action (or 0 at start)
        user_idx: int,               # user index
        h: Optional[torch.Tensor] = None,  # (1,1,HIDDEN_DIM)
    ) -> Tuple[torch.Tensor, torch.Tensor]:

        # ---- shape fixes: ensure (1,2,H,W) ----
        # קלטים אפשריים: (2,H,W) או (1,2,H,W) או (B,2,H,W)
        if board_2ch.dim() == 3:
            # (2,H,W) -> (1,2,H,W)
            board_2ch = board_2ch.unsqueeze(0)
        elif board_2ch.dim() == 5 and board_2ch.size(0) == 1:
            # (1,1,2,H,W) -> (1,2,H,W) אם מישהו עטף בבאץ' נוסף
            board_2ch = board_2ch.squeeze(0)

        assert board_2ch.dim() == 4 and board_2ch.size(1) == 2, \
            f"expected (1,2,H,W), got {tuple(board_2ch.shape)}"

        device = board_2ch.device

        bf = self.cnn(board_2ch)                         # (1,128)
        abits = int_to_8bits(int(action_token), device)  # (1,8) on same device
        uemb = self.user_emb(torch.tensor([user_idx], device=device))  # (1,32)

        x = torch.cat([bf, abits, uemb], dim=1)  # (1,168)
        x = x.unsqueeze(1)                       # (1,1,168) — time=1

        out, h_new = self.gru(x, h)              # out: (1,1,128); h_new: (1,1,128)
        logits = self.head(out.squeeze(1))       # (1,NUM_ACTIONS)
        return logits, h_new
