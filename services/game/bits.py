import torch
from .settings import DTYPE, COLOR_BITS, BIT_IS_PLAYER, BIT_R0, BIT_R1, BIT_G0, BIT_G1, BIT_B0, BIT_B1

def set_bit(v: torch.Tensor, bit: int, one: bool) -> torch.Tensor:
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

def inc_color(v: torch.Tensor) -> torch.Tensor:
    for (b0, b1) in COLOR_BITS.values():
        curr = int(get2(v, b0, b1))
        v = set2(v, b0, b1, (curr + 1) % 4)
    return v

def make_color(r2: int, g2: int, b2: int) -> torch.Tensor:
    v = torch.tensor(0, dtype=DTYPE)
    v = set2(v, BIT_R0, BIT_R1, r2)
    v = set2(v, BIT_G0, BIT_G1, g2)
    v = set2(v, BIT_B0, BIT_B1, b2)
    return v

def with_player(v: torch.Tensor) -> torch.Tensor:
    return set_bit(v, BIT_IS_PLAYER, True)

def without_player(v: torch.Tensor) -> torch.Tensor:
    return set_bit(v, BIT_IS_PLAYER, False)

