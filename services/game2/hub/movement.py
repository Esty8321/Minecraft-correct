from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import torch
from .types import Direction, Coord, PlayerState
from .board_utils import BoardUtils
from .world import WorldService
from ..data.db_chunks import ChunkDB
from  ..data.db_players import PlayerDB
from ..core.bits import compose_entry_cells
from .chunk_players import ChunkPlayers
@dataclass
class MoveResult:
   moved: bool
   old_chunk_id: Optional[str] = None

class MovementService:
    """Handles player movement logic both within and between chunks.
     the board state and player database accordingly."""
    def __init__(self, world: WorldService, chunk_db: ChunkDB, player_db: PlayerDB, chunk_players: ChunkPlayers) -> None:
        self.world = world
        
        self.chunk_db = chunk_db
        self.player_db = player_db
        self.chunk_players = chunk_players
 
    async def apply_move(self, state: PlayerState, dr: int, dc: int) -> MoveResult:
        nr, nc = state.pos.row + dr, state.pos.col + dc
        if BoardUtils.in_bounds(nr, nc):
            board = self.world.ensure_chunk(state.chunk_id)
            if not self.chunk_players.is_cell_free(state.chunk_id, nr, nc):
                return MoveResult(False)
            await self.move_within_chunk(state, board, nr, nc)
            return MoveResult(True, None)

        direction = BoardUtils.edge_direction(nr, nc)
        moved, old_chunk_id = await self._transfer_between_chunks(state, direction)
        return MoveResult(moved, old_chunk_id if moved else None)
    
    async def move_within_chunk(self, state: PlayerState, board: torch.Tensor, nr: int, nc: int) -> None:
        board[state.pos.row, state.pos.col] = state.underlying_cell
        new_underlying = board[nr, nc].clone()
        
        color = state.color
        board[nr, nc] = color
        state.pos = Coord(nr, nc)   
        self.player_db.save_position(state.user_id, state.chunk_id, nr, nc)
        self.chunk_players.update_position(state.chunk_id, state.user_id, nr, nc)
        state.underlying_cell = new_underlying
        
    async def _transfer_between_chunks(self, state: PlayerState, direction: Direction) -> Tuple[bool, str]:
        """Move player between chunks - keep both chunks in memory."""
        old_chunk_id = state.chunk_id
        old_board = self.world.ensure_chunk(old_chunk_id)
        new_chunk_id = WorldService.neighbor_chunk_id(old_chunk_id, direction)
        new_board = self.world.ensure_chunk(new_chunk_id)
        target = BoardUtils.edge_target_for_direction(state, direction)

     
        if not self.chunk_players.is_cell_free(state.chunk_id, target.row, target.col):
                return False, old_chunk_id
            
        ##??chekc if I need to chekc is_empty that the user wil not chage the color of the pixel if it already colored
        async with self.world._lock_for(old_chunk_id):
            old_board[state.pos.row, state.pos.col] = state.underlying_cell
            self.world._mark_dirty(old_chunk_id)
   
        async with self.world._lock_for(new_chunk_id):
            new_under, new_vis = compose_entry_cells(new_board, target.row, target.col, state.color)
            new_board[target.row, target.col] = new_vis
            self.world._mark_dirty(new_chunk_id)

        state.chunk_id = new_chunk_id
        state.pos = target
        state.underlying_cell = new_under
        state.visible_cell = new_vis
        
        ##??chekc how can I do it only one time instead two
        self.player_db.save_position(state.user_id,state.chunk_id,state.pos.row,state.pos.col)
        self.chunk_players.move_player(old_chunk_id, new_chunk_id, state.user_id, target.row, target.col)
        return True, old_chunk_id
        
