from __future__ import annotations
import random
import torch
from ..core.settings import W, H, BIT_IS_PLAYER
from ..core.bits import get_bit
from .types import Coord, PlayerState, Direction

class BoardUtils:
    """Provides helper methods for board geometry: checking bounds, emptiness, edges, and random spawn cells."""

    @staticmethod
    def is_empty(board: torch.Tensor, r: int, c: int) -> bool:
        return int(get_bit(board[r, c], BIT_IS_PLAYER)) == 0

    @staticmethod
    def in_bounds(r: int, c: int) -> bool:
        return 0 <= r < H and 0 <= c < W

    @staticmethod
    def edge_direction(nr: int, nc: int) -> Direction:
        if nr < 0:
            return "up"
        if nr >= H:
            return "down"
        if nc < 0:
            return "left"
        return "right"

    @staticmethod
    def edge_target_for_direction(state: PlayerState, direction: Direction) -> Coord:
        if direction == "up":
            return Coord(H - 1, state.pos.col)
        if direction == "down":
            return Coord(0, state.pos.col)
        if direction == "left":
            return Coord(state.pos.row, W - 1)
        return Coord(state.pos.row, 0)

    @staticmethod
    def random_empty_cell(board: torch.Tensor) -> Coord:
        """Find a random empty cell on the board."""
        for _ in range(4096):
            r, c = random.randrange(H), random.randrange(W)
            if BoardUtils.is_empty(board, r, c):
                return Coord(r, c)
        # fallback center
        return Coord(H // 2, W // 2)
