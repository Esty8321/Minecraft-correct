#V
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
@dataclass
class MoveResult:
   moved: bool
   old_chunk_id: Optional[str] = None

class MovementService:
    """Handles player movement logic both within and between chunks.
     the board state and player database accordingly."""
    def __init__(self, world: WorldService, chunk_db: ChunkDB, player_db: PlayerDB) -> None:
        self.world = world
        
        self.chunk_db = chunk_db
        self.player_db = player_db
 
    async def apply_move(self, state: PlayerState, dr: int, dc: int) -> MoveResult:
        nr, nc = state.pos.row + dr, state.pos.col + dc
        if BoardUtils.in_bounds(nr, nc):
            board = self.world.ensure_chunk(state.chunk_id)
            if not BoardUtils.is_empty(board, nr, nc):
                return MoveResult(False)
            await self._move_within_chunk(state, board, nr, nc)
            return MoveResult(True, None)

        direction = BoardUtils.edge_direction(nr, nc)
        moved, old_chunk_id = await self._transfer_between_chunks(state, direction)
        return MoveResult(moved, old_chunk_id if moved else None)
    
    
    async def _move_within_chunk(self, state: PlayerState, board: torch.Tensor, nr: int, nc: int) -> None:
        board[state.pos.row, state.pos.col] = state.underlying_cell
        new_under, new_vis = compose_entry_cells(board, nr, nc, state.color)
        board[nr, nc] = new_vis
        self.chunk_db.save_chunk(state.chunk_id, board)
        state.pos = Coord(nr, nc)
        state.underlying_cell = new_under
        state.visible_cell = new_vis
        self.player_db.save_position(state.user_id ,state.chunk_id,state.pos.row,state.pos.col)
    
    
    async def _transfer_between_chunks(self, state: PlayerState, direction: Direction) -> Tuple[bool, str]:
        old_chunk_id = state.chunk_id
        old_board = self.world.ensure_chunk(old_chunk_id)
        new_chunk_id = WorldService.neighbor_chunk_id(old_chunk_id, direction)
        new_board = self.world.ensure_chunk(new_chunk_id)
        target = BoardUtils.edge_target_for_direction(state, direction)

        if not BoardUtils.is_empty(new_board, target.row, target.col):
            return False, old_chunk_id

        async with self.world._lock_for(old_chunk_id):
            old_board[state.pos.row, state.pos.col] = state.underlying_cell
            self.chunk_db.save_chunk(old_chunk_id, old_board)


        async with self.world._lock_for(new_chunk_id):
            new_under, new_vis = compose_entry_cells(new_board, target.row, target.col, state.color)
            new_board[target.row, target.col] = new_vis
            self.chunk_db.save_chunk(new_chunk_id, new_board)

        state.chunk_id = new_chunk_id
        state.pos = target
        state.underlying_cell = new_under
        state.visible_cell = new_vis
        self.player_db.save_position(state.user_id,state.chunk_id,state.pos.row,state.pos.col)
        return True, old_chunk_id
        
