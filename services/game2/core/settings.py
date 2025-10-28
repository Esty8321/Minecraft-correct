#V
from pathlib import Path
import torch

# Board size
W = H = 64
DTYPE = torch.uint8

# Bit layout
BIT_IS_PLAYER_IDX = 0
BIT_HAS_LINK_IDX  = 1 
BIT_R0_IDX, BIT_G0_IDX, BIT_B0_IDX = 2, 3, 4
BIT_R1_IDX, BIT_G1_IDX, BIT_B1_IDX = 5, 6, 7

COLOR_BITS = {
    "r": (BIT_R0_IDX, BIT_R1_IDX),
    "g": (BIT_G0_IDX, BIT_G1_IDX),
    "b": (BIT_B0_IDX, BIT_B1_IDX),
}

# Data paths
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "world.db"
PLAYERS_DB_PATH = DATA_DIR / "players.db"
SCROLLS_JSON_PATH = DATA_DIR / "message.json"##to change this name to scrolls
HISTORY_JSON_PATH  = DATA_DIR / "history.json"
