# services/game2/models/bot_gru_v2.py
from __future__ import annotations
import torch
import torch.nn as nn

NUM_ACTIONS = 6
HIDDEN_DIM = 128
USER_EMB_DIM = 32
BOARD_FEAT_DIM = 128
ACTION_BITS = 8
INPUT_DIM = BOARD_FEAT_DIM + 32 + USER_EMB_DIM  # (board) + (proj(action_bits)) + (user_emb)

def bits8_tensor(a: int) -> torch.Tensor:
    bits = [(a >> i) & 1 for i in range(8)]
    return torch.tensor(bits, dtype=torch.float32).unsqueeze(0)

class CoordConv(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B,1,H,W) -> concat coord channels
        B, _, H, W = x.shape
        yy = torch.linspace(-1, 1, steps=H, device=x.device).view(1,1,H,1).expand(B,1,H,W)
        xx = torch.linspace(-1, 1, steps=W, device=x.device).view(1,1,1,W).expand(B,1,H,W)
        return torch.cat([x, yy, xx], dim=1)  # (B,3,H,W)

class ResBlock(nn.Module):
    def __init__(self, c: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(c, c, 3, padding=1), nn.ReLU(),
            nn.Conv2d(c, c, 3, padding=1)
        )
        self.act = nn.ReLU()
    def forward(self, x):
        return self.act(x + self.net(x))

class BoardEncoder(nn.Module):
    def __init__(self, out_dim=BOARD_FEAT_DIM):
        super().__init__()
        self.coord = CoordConv()
        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(),
            ResBlock(32),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            ResBlock(64),
            nn.AdaptiveAvgPool2d((1,1))
        )
        self.proj = nn.Linear(64, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dtype != torch.float32:
            x = x.float() / 255.0
        h = self.coord(x)
        h = self.stem(h).flatten(1)       # (B,64)
        return self.proj(h)               # (B,128)

class GRUPolicyV2(nn.Module):
    def __init__(self, num_users: int):
        super().__init__()
        self.user_emb = nn.Embedding(num_users, USER_EMB_DIM)
        self.board = BoardEncoder(BOARD_FEAT_DIM)
        self.action_proj = nn.Sequential(
            nn.Linear(ACTION_BITS, 32),
            nn.ReLU(),
        )
        self.ln_in = nn.LayerNorm(INPUT_DIM)
        self.gru = nn.GRU(INPUT_DIM, HIDDEN_DIM, batch_first=True)
        self.dropout = nn.Dropout(p=0.1)
        self.head = nn.Sequential(
            nn.Linear(HIDDEN_DIM, HIDDEN_DIM),
            nn.ReLU(),
            nn.Linear(HIDDEN_DIM, NUM_ACTIONS)
        )

    def forward_step(self, board, action_token: int, user_idx: int, h=None):
        bf = self.board(board)                          # (1,128)
        abits = bits8_tensor(int(action_token))         # (1,8)
        ap = self.action_proj(abits)                    # (1,32)
        uemb = self.user_emb(torch.tensor([user_idx]))  # (1,32)
        x = torch.cat([bf, ap, uemb], dim=1)            # (1,168)
        x = self.ln_in(x).unsqueeze(1)                  # (1,1,168)
        out, h_new = self.gru(x, h)
        out = self.dropout(out.squeeze(1))
        logits = self.head(out).unsqueeze(0)            # (1,6)
        return logits, h_new
