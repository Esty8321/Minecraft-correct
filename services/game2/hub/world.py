from __future__ import annotations
import asyncio, logging
from typing import Dict, Tuple, Set
import torch
from .types import Coord, PlayerState, Direction
from .board_utils import BoardUtils
from ..core.settings import W, H, DTYPE, BIT_FRUIT_IDX
from ..core.bits import get_bit
from ..data.db_chunks import ChunkDB
from ..data.db_players import PlayerDB
from ..data.user_logs import UserActionLogger
from .chunk_players import ChunkPlayers
from ..core.ids import chunk_id_from_coords, coords_from_chunk_id
import random

logger = logging.getLogger(__name__)

class WorldService:
    """Manages the game world, chunks, and player positions."""
    def __init__(self, chunk_db: ChunkDB, player_db: PlayerDB, 
                 user_logs: UserActionLogger, chunk_players: ChunkPlayers) -> None:
        self.chunk_db = chunk_db
        self.player_db = player_db
        self.user_logs = user_logs


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
            is_new = False
        except FileNotFoundError:
            board = torch.zeros((H, W), dtype=DTYPE)
            is_new = True
                    
        self._chunks[chunk_id] = board
        if is_new:
            self._scatter_fruits(chunk_id, board)
        return board


    
    def _scatter_fruits(self, chunk_id: str, board: torch.Tensor):
       import random

       FRUIT_COUNT = 5
       placed = 0
       
       FRUIT_VALUE = 2 ** BIT_FRUIT_IDX

       while placed < FRUIT_COUNT:
           r = random.randrange(H)
           c = random.randrange(W)   

           if board[r, c].item() == 0:
               board[r, c] = torch.tensor(FRUIT_VALUE, dtype=DTYPE)
               placed += 1

       self.chunk_db.save_chunk(chunk_id, board)## mabye enough to mark as dirty
           
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
        
        import random
        for _ in range(4096):
            r, c = random.randrange(H), random.randrange(W)
            if self.chunk_players.is_cell_free(self.root_chunk_id, r, c):
                return self.root_chunk_id, Coord(r,c)
         
        return Coord(H // 2, W // 2)
 
      

    async def spawn_player(self, user_id: str, chunk_id: str, spawn: Coord) -> PlayerState:
           board = self.ensure_chunk(chunk_id)           
           return PlayerState(
               user_id=user_id,
               chunk_id=chunk_id,
               pos=spawn,
           )
                    
                     
    def despawn_player(self, state: PlayerState) -> None:#mabye I can dlete this function??
        """When player disconnects."""
        self.player_db.upsert(state.user_id, state.chunk_id, state.pos.row, state.pos.col)
      
   
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
