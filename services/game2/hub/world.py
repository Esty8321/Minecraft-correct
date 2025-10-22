from __future__ import annotations
import asyncio
import logging
from typing import Dict, Tuple
import torch
from .types import Coord, PlayerState
from .helper import random_empty_cell
from ..core.settings import W, H, DTYPE
from ..core.bits import with_player, without_player, get_bit, set_bit, get_player_color_by_user_id
from ..core.ids import chunk_id_from_coords
from ..data.db_chunks import load_chunk, save_chunk
from ..data.db_players import get_player_position, save_player_position
from ..core.settings import BIT_HAS_LINK


logger = logging.getLogger(__name__)

class WorldService:
    def __init__(self) -> None:
        self._chunks: Dict[str, torch.Tensor] = {}
        self._chunk_locks: Dict[str, asyncio.Lock] = {}
        self.root_chunk_id = chunk_id_from_coords(0, 0)
        self.ensure_chunk(self.root_chunk_id)#


    def _lock_for(self, chunk_id: str) -> asyncio.Lock:
        if chunk_id not in self._chunk_locks:
          self._chunk_locks[chunk_id] = asyncio.Lock()
        return self._chunk_locks[chunk_id]

    def ensure_chunk(self, chunk_id: str) -> torch.Tensor:
        if chunk_id in self._chunks:
         return self._chunks[chunk_id]
        board = load_chunk(chunk_id)
        if board is None:
         board = torch.zeros((H, W), dtype=DTYPE)
        save_chunk(chunk_id, board)
        self._chunks[chunk_id] = board
        return board

    @staticmethod
    def compose_entry_cells(board: torch.Tensor, r: int, c: int, color: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        dest_val: int = int(board[r, c].item())
        new_under_val: int = int(without_player(dest_val))
        new_vis_val: int = int(with_player(color))
        if get_bit(dest_val, BIT_HAS_LINK):
            new_vis_val = int(set_bit(new_vis_val, BIT_HAS_LINK, True))
        new_under = torch.tensor(new_under_val, dtype=DTYPE)
        new_vis   = torch.tensor(new_vis_val,   dtype=DTYPE)
        return new_under, new_vis

    async def get_spawn_position(self, user_id: str) -> Tuple[str, Coord]:
        pos = get_player_position(user_id)
        if pos:
            chunk_id, row, col = pos
            board = self.ensure_chunk(chunk_id)
            return chunk_id, Coord(row, col)
        board = self.ensure_chunk(self.root_chunk_id)
        return self.root_chunk_id, random_empty_cell(board)

    async def spawn_player(self, user_id: str, chunk_id: str, spawn: Coord) -> PlayerState:
        color = get_player_color_by_user_id(user_id)
        lock = self._lock_for(chunk_id)
        async with lock:
            board = self.ensure_chunk(chunk_id)
            underlying = without_player(board[spawn.row, spawn.col])
            visible = with_player(color)
            board[spawn.row, spawn.col] = visible
            save_chunk(chunk_id, board)
        save_player_position(user_id, chunk_id, spawn.row, spawn.col)
        return PlayerState(user_id=user_id,chunk_id=chunk_id, pos=spawn, visible_cell=visible.clone(), underlying_cell=underlying, color=color)


    async def despawn_player(self, state: PlayerState) -> None:
        lock = self._lock_for(state.chunk_id)
        async with lock:
            board = self.ensure_chunk(state.chunk_id)
            board[state.pos.row, state.pos.col] = state.underlying_cell
            save_chunk(state.chunk_id, board)
        if state.user_id:
         save_player_position(state.user_id, state.chunk_id, state.pos.row, state.pos.col)