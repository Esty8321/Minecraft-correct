from __future__ import annotations
import asyncio, logging
from typing import Dict, Tuple, Set
import torch
from .types import Coord, PlayerState, Direction
from .board_utils import BoardUtils
from ..core.settings import W, H, DTYPE
from ..core.bits import get_player_color_by_user_id
from ..data.db_chunks import ChunkDB
from ..data.db_players import PlayerDB
from ..data.db_history import  PlayerActionHistory
from .chunk_players import ChunkPlayers
from ..core.ids import chunk_id_from_coords, coords_from_chunk_id

logger = logging.getLogger(__name__)

class WorldService:
    """Manages the game world, chunks, and player positions."""
    def __init__(self, chunk_db: ChunkDB, player_db: PlayerDB, 
                 player_actions_history: PlayerActionHistory, chunk_players: ChunkPlayers) -> None:
        self.chunk_db = chunk_db
        self.player_db = player_db
        self.player_actions_history = player_actions_history


        self._chunks: Dict[str, torch.Tensor] = {}
        self._chunk_locks: Dict[str, asyncio.Lock] = {}
        self._dirty: Set[str] = set()

        self.root_chunk_id = chunk_id_from_coords(0, 0)
        self.ensure_chunk(self.root_chunk_id)
        
        self.chunk_players = chunk_players
        asyncio.create_task(self._flush_loop())

    def _lock_for(self, chunk_id: str) -> asyncio.Lock:
        if chunk_id not in self._chunk_locks:
            self._chunk_locks[chunk_id] = asyncio.Lock()
        return self._chunk_locks[chunk_id]

    def _mark_dirty(self, chunk_id: str) -> None:
        self._dirty.add(chunk_id)

    def ensure_chunk(self, chunk_id: str) -> torch.Tensor:
        """Ensure chunk is loaded or create a new one."""
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
        """Periodically write all dirty chunks to disk."""
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
        """Return stored or random spawn position for a player."""
        pos = self.player_db.get_position(user_id)
        if pos:
            chunk_id, row, col = pos
            board = self.ensure_chunk(chunk_id)
            return chunk_id, Coord(row, col)
        board = self.ensure_chunk(self.root_chunk_id)
        return self.root_chunk_id, BoardUtils.random_empty_cell(board)
      

    async def spawn_player(self, user_id: str, chunk_id: str, spawn: Coord) -> PlayerState:
           """Spawn player into chunk, assigning color directly if not already placed."""
           print("In the spawn function")
           color = get_player_color_by_user_id(user_id)
           lock = self._lock_for(chunk_id)

           async with lock:
               board = self.ensure_chunk(chunk_id)

               if BoardUtils.is_empty(board, spawn.row, spawn.col):
                   underlying = torch.zeros_like(board[spawn.row, spawn.col])
                   board[spawn.row, spawn.col] = color
                
                   self._mark_dirty(chunk_id)
               else:    
                   underlying = board[spawn.row, spawn.col].clone()
   
           self.player_db.save_position(user_id, chunk_id, spawn.row, spawn.col)
           
           return PlayerState(
               user_id=user_id,
               chunk_id=chunk_id,
               pos=spawn,
               visible_cell=color,
               underlying_cell=underlying,
               color=color,
           )
                    
                     
    async def despawn_player(self, state: PlayerState) -> None:
        """When player disconnects."""
        lock = self._lock_for(state.chunk_id)
        async with lock:
            board = self.ensure_chunk(state.chunk_id)
            board[state.pos.row, state.pos.col] = state.underlying_cell
            self._mark_dirty(state.chunk_id)
            self.chunk_db.save_chunk(state.chunk_id, board)
        self.player_db.save_position(state.user_id, state.chunk_id, state.pos.row, state.pos.col)
        self.maybe_unload_chunk(state.chunk_id)

    def maybe_unload_chunk(self, chunk_id: str) -> None:
        """Unload chunk from memory if no players remain."""
        players = self.chunk_players.get_players_in_chunk(chunk_id)
        if not players and chunk_id in self._chunks:
            del self._chunks[chunk_id]
            logger.info(f"Unloaded chunk {chunk_id} from memory")

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
