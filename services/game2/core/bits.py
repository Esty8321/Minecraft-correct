import hashlib
import torch
from .settings import (
    DTYPE, COLOR_BITS,
    BIT_IS_PLAYER, BIT_R0, BIT_R1, BIT_G0, BIT_G1, BIT_B0, BIT_B1
)  

def set_bit(v: torch.Tensor, bit: int, one: bool) -> torch.Tensor:
    """Set/Clear single bit on an 8-bit tensor value."""
    mask = torch.tensor(1 << bit, dtype=DTYPE)
    return (v | mask) if one else (v & (~mask & torch.tensor(0xFF, dtype=DTYPE)))

def get_bit(v: torch.Tensor, bit: int) -> torch.Tensor:
    return (v >> bit) & 1

def get2(v: torch.Tensor, b0: int, b1: int) -> torch.Tensor:
    return ((v >> b1) & 1) * 2 + ((v >> b0) & 1)


def set2(v: torch.Tensor, b0: int, b1: int, x: int) -> torch.Tensor:
    x &= 3
    v = v & (~(torch.tensor((1 << b0) | (1 << b1), dtype=DTYPE)) & torch.tensor(0xFF, dtype=DTYPE))
    if x & 1: v = v | torch.tensor(1 << b0, dtype=DTYPE)
    if x & 2: v = v | torch.tensor(1 << b1, dtype=DTYPE)
    return v

def make_color(r2: int, g2: int, b2: int) -> torch.Tensor:
    """Compose color (2 bits per channel) into a single 8-bit value without player flag."""
    v = torch.tensor(0, dtype=DTYPE)
    v = set2(v, BIT_R0, BIT_R1, r2)
    v = set2(v, BIT_G0, BIT_G1, g2)
    v = set2(v, BIT_B0, BIT_B1, b2)
    return v

def with_player(v: torch.Tensor) -> torch.Tensor:
    return set_bit(v, BIT_IS_PLAYER, True)

def without_player(v: torch.Tensor) -> torch.Tensor:
    return set_bit(v, BIT_IS_PLAYER, False)

def get_player_color_by_user_id(user_id: str | int) -> torch.Tensor:
    """Stable color per user-id using sha256 digest."""
    digest = hashlib.sha256(str(user_id).encode("utf-8")).digest()
    return make_color(digest[0] & 3, digest[1] & 3, digest[2] & 3)
