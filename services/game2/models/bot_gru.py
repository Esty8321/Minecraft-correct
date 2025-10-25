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

def int_to_8bits(a: int) -> torch.Tensor:
    bits = [(a >> i) & 1 for i in range(8)]
    return torch.tensor(bits, dtype=torch.float32).unsqueeze(0)  # (1,8)

class SmallBoardCNN(nn.Module):
    def __init__(self, out_dim=BOARD_FEAT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),  # 32x32
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),  # 16x16
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((1,1)),     # (B,128,1,1)
        )
        self.proj = nn.Linear(128, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B,1,H,W), עדיף לנרמל ל- [0..1]
        if x.dtype != torch.float32:
            x = x.float() / 255.0
        h = self.net(x).flatten(1)          # (B,128)
        return self.proj(h)                 # (B,BOARD_FEAT_DIM)

class GRUPolicy(nn.Module):
    def __init__(self, num_users: int):
        super().__init__()
        self.user_emb = nn.Embedding(num_users, USER_EMB_DIM)
        self.cnn = SmallBoardCNN(BOARD_FEAT_DIM)
        self.gru = nn.GRU(INPUT_DIM, HIDDEN_DIM, batch_first=True)
        self.head = nn.Linear(HIDDEN_DIM, NUM_ACTIONS)

    def forward_step(
    self,
    board: torch.Tensor,     # (1,1,H,W) expected
    action_token: int,       # last action (or 0 at start)
    user_idx: int,           # user index
    h: Optional[torch.Tensor] = None,  # (1,1,HIDDEN_DIM)
) -> Tuple[torch.Tensor, torch.Tensor]:
        # ---- FIX START ----
        # Ensure correct shape: (B, 1, H, W)
        if board.dim() == 5:
            board = board.squeeze(0)  # remove the extra dimension (1,1,H,W)
        elif board.dim() == 3:
            board = board.unsqueeze(0)  # add batch dimension if missing
        # ---- FIX END ----

        bf = self.cnn(board)                 # (1,128)
        abits = int_to_8bits(int(action_token))  # (1,8)
        uemb = self.user_emb(torch.tensor([user_idx]))  # (1,32)

        x = torch.cat([bf, abits, uemb], dim=1)  # (1,168)
        x = x.unsqueeze(1)                       # (1,1,168) — time=1

        out, h_new = self.gru(x, h)              # out: (1,1,128); h_new: (1,1,128)
        logits = self.head(out.squeeze(1))       # (1,NUM_ACTIONS)
        return logits, h_new  # return logits for next action + new hidden
