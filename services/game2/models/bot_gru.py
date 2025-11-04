# services/game2/models/bot_gru.py
from __future__ import annotations
import torch
import torch.nn as nn
from typing import Optional, Tuple

# --- הגדרות בסיס ---
NUM_ACTIONS = 7            # 4 תזוזות + COLOR + DM/CHAT + SLEEP
HIDDEN_DIM = 128
USER_EMB_DIM = 32
BOARD_FEAT_DIM = 128
ACTION_BITS = 8
TIME_FEAT_DIM = 1          # prev_delta_norm סקלר אחד
INPUT_DIM = BOARD_FEAT_DIM + ACTION_BITS + USER_EMB_DIM + TIME_FEAT_DIM  # 128 + 8 + 32 + 1 = 169

def int_to_8bits(a: int) -> torch.Tensor:
    bits = [(a >> i) & 1 for i in range(8)]
    return torch.tensor(bits, dtype=torch.float32).unsqueeze(0)  # (1,8)

class SmallBoardCNN(nn.Module):
    """
    CNN קטן שמקבל 2 ערוצים: ערוץ-0 = board, ערוץ-1 = occupancy.
    מחזיר וקטור פיצ'רים בגודל BOARD_FEAT_DIM.
    """
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
        # x: (B,2,H,W) — נרמול ל-[0..1] אם לא float
        if x.dtype != torch.float32:
            x = x.float() / 255.0
        h = self.net(x).flatten(1)      # (B,128)
        return self.proj(h)             # (B,BOARD_FEAT_DIM)

class GRUPolicy(nn.Module):
    """
    מודל חיזוי פעולה (7 קטגוריות) + רגרסיית משך שינה (normalized).
    קלט: board_2ch (B,2,H,W), prev_action_token (int), user_idx (int), prev_delta_norm (float).
    פלט: logits (B,NUM_ACTIONS), h_new (1,B,HIDDEN_DIM), sleep_reg (B,1)
    """
    def __init__(self, num_users: int):
        super().__init__()
        self.user_emb = nn.Embedding(num_users, USER_EMB_DIM)
        self.cnn = SmallBoardCNN(BOARD_FEAT_DIM, in_channels=2)
        self.gru = nn.GRU(INPUT_DIM, HIDDEN_DIM, batch_first=True)
        self.head = nn.Linear(HIDDEN_DIM, NUM_ACTIONS)   # סיווג פעולה
        self.sleep_head = nn.Sequential(                  # רגרסיה לזמן שינה מנורמל [0..1]
            nn.Linear(HIDDEN_DIM, HIDDEN_DIM),
            nn.ReLU(),
            nn.Linear(HIDDEN_DIM, 1),
            nn.Sigmoid(),  # מחזיר 0..1
        )

    def _pack_input_vec(
        self, board_2ch: torch.Tensor, action_token: int, user_idx: int, prev_delta_norm: float
    ) -> torch.Tensor:
        """
        מרכיב וקטור קלט יחיד באורך INPUT_DIM: [board_feat | action_bits | user_emb | prev_delta_norm]
        """
        bf = self.cnn(board_2ch)                             # (1,BOARD_FEAT_DIM)
        abits = int_to_8bits(int(action_token))              # (1,8)
        uemb = self.user_emb(torch.tensor([user_idx]))       # (1,USER_EMB_DIM)
        dfeat = torch.tensor([[float(prev_delta_norm)]], dtype=torch.float32)  # (1,1)
        x = torch.cat([bf, abits, uemb, dfeat], dim=1)       # (1, INPUT_DIM)
        return x

    def forward_step(
        self,
        board_2ch: torch.Tensor,     # (1,2,H,W)
        action_token: int,           # last action (or 0 at start)
        user_idx: int,               # user index
        prev_delta_norm: float,      # normalized time gap since last action (0..1)
        h: Optional[torch.Tensor] = None,  # (1,1,HIDDEN_DIM)
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # מוודאים batch=1
        if board_2ch.dim() == 4:
            board_2ch = board_2ch  # (1,2,H,W) כבר טוב
        elif board_2ch.dim() == 5:
            board_2ch = board_2ch.squeeze(0)
        else:
            board_2ch = board_2ch.unsqueeze(0)  # (1,2,H,W)

        x = self._pack_input_vec(board_2ch, action_token, user_idx, prev_delta_norm)  # (1,INPUT_DIM)
        x = x.unsqueeze(1)  # (1,1,INPUT_DIM) כצעד זמן יחיד
        out, h_new = self.gru(x, h)                     # out: (1,1,HIDDEN_DIM)
        out1 = out.squeeze(1)                           # (1,HIDDEN_DIM)
        logits = self.head(out1)                        # (1,NUM_ACTIONS)
        sleep_reg = self.sleep_head(out1)               # (1,1) normalized
        return logits, h_new, sleep_reg

    # אופציונלי: עיבוד באצ' קטן בלולאה
    def forward_step_batch(
        self,
        board_2ch: torch.Tensor,       # (B,2,H,W)
        prev_tokens: torch.Tensor,     # (B,)
        user_idx: torch.Tensor,        # (B,)
        prev_delta_norm: torch.Tensor, # (B,)
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor], torch.Tensor]:
        B = board_2ch.size(0)
        outs, sleeps = [], []
        h = None
        for i in range(B):
            logits, h, sleep_reg = self.forward_step(
                board_2ch[i:i+1],
                int(prev_tokens[i]),
                int(user_idx[i]),
                float(prev_delta_norm[i].item()) if prev_delta_norm.dim()>0 else float(prev_delta_norm)
            )
            outs.append(logits)
            sleeps.append(sleep_reg)
        return torch.cat(outs, dim=0), h, torch.cat(sleeps, dim=0)  # (B,NUM_ACTIONS), h, (B,1)
