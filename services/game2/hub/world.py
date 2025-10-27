from __future__ import annotations
import asyncio, math
import logging
from typing import Dict, Tuple, Optional, Set
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
        self.chunk_db = chunk_db
        self.player_db =player_db
        self.player_actions_history = player_actions_history
        
        self._chunks: Dict[str, torch.Tensor] = {}
        self._chunk_locks: Dict[str, asyncio.Lock] = {}
        self._dirty: Set[str] = set()
       
        self.root_chunk_id = chunk_id_from_coords(0, 0)
        self.ensure_chunk(self.root_chunk_id)
  
        asyncio.create_task(self._flush_loop())
        
    def _lock_for(self, chunk_id: str) -> asyncio.Lock:
        if chunk_id not in self._chunk_locks:
          self._chunk_locks[chunk_id] = asyncio.Lock()
        return self._chunk_locks[chunk_id] 

    def _mark_dirty(self, chunk_id: str)-> None:
        self._dirty.add(chunk_id)
        
    def ensure_chunk(self, chunk_id: str) -> torch.Tensor:
        if chunk_id in self._chunks:
         return self._chunks[chunk_id]
        try:
            board = self.chunk_db.load_chunk(chunk_id)
        except FileNotFoundError:
             board = torch.zeros((H, W), dtype=DTYPE)
             self.chunk_db.save_chunk(chunk_id, board)
        self._chunks[chunk_id] = board
        return board


    async def _flush_loop(self):
        """Periodically write all dirty chunks to disk"""
        while True:
            try:
                dirty_copy = list(self._dirty)
                for chunk_id in dirty_copy:
                    async with self._lock_for(chunk_id):
                        board = self._chunks.get(chunk_id)
                        if board is not None:
                            self.chunk_db.save_chunk(chunk_id, board)
                            self._dirty.discard(chunk_id)
                await asyncio.sleep(5)
            except Exception:
                logger.exception("Error during flush loop")
                
                
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
         
    
    async def despawn_player(self, state:PlayerState) -> None:
        """When player disconnects."""
        lock = self._lock_for(state.chunk_id)
        async with lock:
            board = self.ensure_chunk(state.chunk_id)
            board[state.pos.row][state.pos.col] = 0
            self._mark_dirty(state.chunk_id)
        self.player_db.save_position(state.user_id, state.chunk_id, state.pos.row, state.pos.col)
        self.mabye_unload_chunk(state.chunk_id)
        
        
    def mabye_unload_chunk(self, chunk_id: str) -> None:
        """Remove chunk from memory if no players are inside."""
        players = self.player_db.list_players_in_chunk(chunk_id)
        if not players and chunk_id in self._chunks:
            del self._chunks[chunk_id]
            logger.info(f"Upload chunk {chunk_id} from memory")
        
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
