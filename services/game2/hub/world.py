#V
from __future__ import annotations
import asyncio, math
import logging
from typing import Dict, Tuple, Optional
import torch
from .types import Coord, PlayerState, Direction
from .board_utils import BoardUtils
from ..core.settings import W, H, DTYPE
from ..core.bits import with_player, without_player, get_player_color_by_user_id
from ..data.db_chunks import  ChunkDB
from ..data.db_players import  PlayerDB
from ..core.settings import BIT_HAS_LINK
import random
from ..core.bits import make_color, set_bit, get_bit, with_player
from ..core.settings import DTYPE, BIT_HAS_LINK
from ..data.db_history import ActionToken, PlayerActionHistory
from ..core.ids import chunk_id_from_coords, coords_from_chunk_id

logger = logging.getLogger(__name__)

class WorldService:
    """
    Manages the game world (chunks and player positions).
    load/save chunks from/to database, maintain an in-memory cach of active chunks , provide thread safe access to each chunk, spawn, despawn players bu updating chunk data, handle color
    """
    def __init__(self, chunk_db: ChunkDB, player_db : PlayerDB,player_actions_history: PlayerActionHistory ) -> None:
        self._chunks: Dict[str, torch.Tensor] = {}
        self._chunk_locks: Dict[str, asyncio.Lock] = {}
        
        self.chunk_db = chunk_db
        self.player_db =player_db
        self.player_actions_history = player_actions_history
       
        self.root_chunk_id = chunk_id_from_coords(0, 0)
        self.ensure_chunk(self.root_chunk_id)
  
  
    def _lock_for(self, chunk_id: str) -> asyncio.Lock:
        if chunk_id not in self._chunk_locks:
          self._chunk_locks[chunk_id] = asyncio.Lock()
        return self._chunk_locks[chunk_id] 


    def ensure_chunk(self, chunk_id: str) -> torch.Tensor:
        if chunk_id in self._chunks:
         return self._chunks[chunk_id]
        board = self.chunk_db.load_chunk(chunk_id)
        if board is None:
         board = torch.zeros((H, W), dtype=DTYPE)
        self.chunk_db.save_chunk(chunk_id, board)
        self._chunks[chunk_id] = board
        return board

    async def get_spawn_position(self, user_id: str) -> Tuple[str, Coord]:
        pos = self.player_db.get_position(user_id)
        if pos:
            chunk_id, row, col = pos
            board = self.ensure_chunk(chunk_id)
            return chunk_id, Coord(row, col)
        board = self.ensure_chunk(self.root_chunk_id)
        return self.root_chunk_id, BoardUtils.random_empty_cell(board)


    async def spawn_player(self, user_id: str, chunk_id: str, spawn: Coord) -> PlayerState:
        color = get_player_color_by_user_id(user_id)
        lock = self._lock_for(chunk_id)
        async with lock:
            board = self.ensure_chunk(chunk_id)
            underlying = without_player(board[spawn.row, spawn.col])
            visible = with_player(color)
            board[spawn.row, spawn.col] = visible
            self.chunk_db.save_chunk(chunk_id, board)
        self.player_db.save_position(user_id, chunk_id, spawn.row, spawn.col)
        return PlayerState(user_id=user_id,chunk_id=chunk_id, pos=spawn, visible_cell=visible.clone(), underlying_cell=underlying, color=color)
         
         
    def find_nearest_player_in_chunk(self, user_id: str)->Optional[str]:
        me = self.player_db.get_position(user_id)
        if not me:
            return None
        chunk_id, my_row, my_col = me
        others = self.player_db.list_players_in_chunk(chunk_id, exclude_id= user_id)
        if not others:
            return None
        board = self.ensure_chunk(chunk_id)##??why need I this line code
        nearest = None
        nearest_dist = float("inf")
        for pid, r, c in others:
            dist = math.hypot(r - my_row, c - my_col)
            if dist < nearest_dist:
                nearest = pid
                nearest_dist = dist
        return nearest
        
    @staticmethod
    def neighbor_chunk_id(chunk_id: str, direction: Direction) -> str:
        cx, cy = coords_from_chunk_id(chunk_id)
        if direction == "up":
            cy -= 1
        elif direction == "down":
            cy += 1
        elif direction == "left":
            cx -= 1
        elif direction == "right":
            cx += 1
        return chunk_id_from_coords(cx, cy)
