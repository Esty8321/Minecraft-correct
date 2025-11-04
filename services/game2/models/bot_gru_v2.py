from __future__ import annotations
import torch
import torch.nn as nn
from typing import Optional, Tuple

NUM_ACTIONS = 7
HIDDEN_DIM = 128
USER_EMB_DIM = 32
BOARD_FEAT_DIM = 128
ACTION_BITS = 8
TIME_FEAT_DIM = 1
INPUT_DIM = BOARD_FEAT_DIM + ACTION_BITS + USER_EMB_DIM + TIME_FEAT_DIM

def int_to_8bits(a: int) -> torch.Tensor:
    bits = [(a >> i) & 1 for i in range(8)]
    return torch.tensor(bits, dtype=torch.float32).unsqueeze(0)

class SmallBoardCNN(nn.Module):
    def __init__(self, out_dim=BOARD_FEAT_DIM, in_channels=2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, 16, 3, padding=1), nn.ReLU(),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((1,1)),
        )
        self.proj = nn.Linear(128, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.float() / 255.0
        h = self.net(x).flatten(1)
        return self.proj(h)

class GRUPolicy(nn.Module):
    def __init__(self, num_users: int):
        super().__init__()
        self.user_emb = nn.Embedding(num_users, USER_EMB_DIM)
        self.cnn = SmallBoardCNN(BOARD_FEAT_DIM, in_channels=2)
        self.gru = nn.GRU(INPUT_DIM, HIDDEN_DIM, batch_first=True)
        self.head = nn.Linear(HIDDEN_DIM, NUM_ACTIONS)
        self.sleep_head = nn.Sequential(
            nn.Linear(HIDDEN_DIM, HIDDEN_DIM),
            nn.ReLU(),
            nn.Linear(HIDDEN_DIM, 1),
            nn.Sigmoid(),
        )
        self.action_fc = nn.Sequential(
            nn.Linear(ACTION_BITS, 16),
            nn.ReLU(),
            nn.Linear(16, ACTION_BITS),
        )
        self.time_fc = nn.Sequential(
            nn.Linear(1, 4),
            nn.ReLU(),
            nn.Linear(4, 1),
        )

    def _pack_input_vec(
        self, board_2ch: torch.Tensor, action_token: int, user_idx: int, prev_delta_norm: float
    ) -> torch.Tensor:
        bf = self.cnn(board_2ch)
        abits = int_to_8bits(int(action_token))
        abits = self.action_fc(abits) * 3.0
        uemb = self.user_emb(torch.tensor([user_idx]))
        dfeat = torch.tensor([[float(prev_delta_norm)]], dtype=torch.float32)
        dfeat = self.time_fc(dfeat)
        x = torch.cat([bf, abits, uemb, dfeat], dim=1)
        return x

    def forward_step(
        self,
        board_2ch: torch.Tensor,
        action_token: int,
        user_idx: int,
        prev_delta_norm: float,
        h: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if board_2ch.dim() == 5:
            board_2ch = board_2ch.squeeze(0)
        elif board_2ch.dim() == 3:
            board_2ch = board_2ch.unsqueeze(0)

        x = self._pack_input_vec(board_2ch, action_token, user_idx, prev_delta_norm)
        x = x.unsqueeze(1)
        out, h_new = self.gru(x, h)
        out1 = out.squeeze(1)
        logits = self.head(out1)
        sleep_reg = self.sleep_head(out1)
        return logits, h_new, sleep_reg

    def forward_step_batch(
        self,
        board_2ch: torch.Tensor,
        prev_tokens: torch.Tensor,
        user_idx: torch.Tensor,
        prev_delta_norm: torch.Tensor,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor], torch.Tensor]:
        B = board_2ch.size(0)
        outs, sleeps = [], []
        h = None
        for i in range(B):
            logits, h, sleep_reg = self.forward_step(
                board_2ch[i:i+1],
                int(prev_tokens[i]),
                int(user_idx[i]),
                float(prev_delta_norm[i].item()) if prev_delta_norm.dim() > 0 else float(prev_delta_norm)
            )
            outs.append(logits)
            sleeps.append(sleep_reg)
        return torch.cat(outs, dim=0), h, torch.cat(sleeps, dim=0)
