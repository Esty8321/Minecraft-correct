from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import torch
from .types import Direction, Coord, PlayerState
from .board_utils import BoardUtils
from .world import WorldService
from ..data.db_chunks import ChunkDB
from  ..data.db_players import PlayerDB
from .chunk_players import ChunkPlayers

from ..core.settings import DTYPE, BIT_FRUIT_IDX
from ..core.bits import get_bit
from ..data.db_scores import ScoresDB
from ..data.user_logs import UserActionLogger
@dataclass
class MoveResult:
   moved: bool
   old_chunk_id: Optional[str] = None

class MovementService:
    """Handles player movement logic both within and between chunks.
     the board state and player database accordingly."""
    def __init__(self, world: WorldService, chunk_db: ChunkDB, chunk_players: ChunkPlayers, scores_db: ScoresDB, scrolls, user_logs: UserActionLogger) -> None:
        self.world = world
        self.scrolls = scrolls
        self.chunk_db = chunk_db
        self.chunk_players = chunk_players
        self.scores_db =scores_db
        self.user_logs = user_logs
        
 
    async def apply_move(self, state: PlayerState, dr: int, dc: int) -> MoveResult:
        nr, nc = state.pos.row + dr, state.pos.col + dc

        if BoardUtils.in_bounds(nr, nc):
            board = self.world.ensure_chunk(state.chunk_id)
            if not self.chunk_players.is_cell_free(state.chunk_id, nr, nc):
                return MoveResult(False)
            old_chunk_id = state.chunk_id
            old_row, old_col = state.pos.row, state.pos.col
            await self.scrolls.on_leave_cell(state.user_id, old_chunk_id, old_row, old_col)
            await self.move_within_chunk(state, board, nr, nc)
            await self.scrolls.on_enter_cell(state.user_id, state.chunk_id, nr, nc)
            return MoveResult(True, None)

        direction = BoardUtils.edge_direction(nr, nc)
        moved, old_chunk_id = await self._transfer_between_chunks(state, direction)
        return MoveResult(moved, old_chunk_id if moved else None)

    
    
    def check_has_fruit(self, state:PlayerState, board, nr, nc):
         cell_val = int(board[nr, nc].item())
    
         if cell_val == 32:
            board[nr, nc] = torch.tensor(0, dtype=DTYPE)
            self.chunk_db.save_chunk(state.chunk_id,board)
            self.scores_db.add_score(state.user_id, 5)
            
    async def move_within_chunk(self, state: PlayerState, board: torch.Tensor, nr: int, nc: int) -> None:
        # old_r, old_c = state.pos.row, state.pos.col##??
        state.pos = Coord(nr, nc)   
        self.chunk_players.update_player_position(state.chunk_id, state.user_id, nr, nc)
        self.check_has_fruit(state, board,nr, nc)

        # ##??new
        # dr = nr - old_r
        # dc = nc - old_c
        # from ..hub.types import MOVE_TOKENS
        # tok = MOVE_TOKENS.get((dr, dc))
        # if tok is not None:
        #     self.action_logger.append(state.user_id, state.chunk_id, nr, nc, int(tok)) 
                       
    async def _transfer_between_chunks(self, state: PlayerState, direction: Direction) -> Tuple[bool, str]:##??can I delte many things from this function
        """Move player between chunks - keep both chunks in memory."""
      

        old_chunk_id = state.chunk_id
        old_board = self.world.ensure_chunk(old_chunk_id)
        new_chunk_id = WorldService.neighbor_chunk_id(old_chunk_id, direction)
        new_board = self.world.ensure_chunk(new_chunk_id)
        target = BoardUtils.edge_target_for_direction(state, direction)
        if not self.chunk_players.is_cell_free(new_chunk_id, target.row, target.col):
            return False, old_chunk_id
        await self.scrolls.on_leave_cell(state.user_id, old_chunk_id, state.pos.row, state.pos.col)
        state.chunk_id = new_chunk_id
        state.pos = target

        self.check_has_fruit(state, new_board, target.row, target.col)
        self.chunk_players.move_player_to_chunk(old_chunk_id, new_chunk_id, state.user_id, target.row, target.col)
        await self.scrolls.on_enter_cell(state.user_id, new_chunk_id, target.row, target.col)

        return True, old_chunk_id

        