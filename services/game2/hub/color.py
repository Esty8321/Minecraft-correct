#V
import random
import torch
from .world import WorldService
from .scrolls import ScrollService
from ..core.settings import DTYPE, BIT_HAS_LINK
from ..core.bits import make_color, get_bit,set_bit,with_player
from .types import PlayerState
from ..data.db_history import ActionToken

class ColorService:
    """Handles player color changes and updates the board and database accordingly."""
    def __init__(self, world: WorldService, scroll: ScrollService):
        self.world = world
        self.scroll = scroll
        
        
    def color_plus_plus(self, state: PlayerState) -> None:
        """Randomize player's base color and update both visible and underlying cells."""
        board = self.world.ensure_chunk(state.chunk_id)
        r, g, b = (random.randint(0, 3) for _ in range(3))
        new_base_color_val = int(make_color(r, g, b))
        old_under_val = int(state.underlying_cell.item()) 
        if get_bit(old_under_val, BIT_HAS_LINK):
            new_base_color_val = int(set_bit(new_base_color_val, BIT_HAS_LINK, True))
        
        state.underlying_cell = torch.tensor(new_base_color_val, dtype=DTYPE)

        visible_with_player_val = int(with_player(state.color))
        if get_bit(new_base_color_val, BIT_HAS_LINK):
            visible_with_player_val = int(set_bit(visible_with_player_val, BIT_HAS_LINK, True))

        board[state.pos.row, state.pos.col] = torch.tensor(visible_with_player_val, dtype=DTYPE)
        self.world.chunk_db.save_chunk(state.chunk_id, board)
     
        self.world.player_actions_history.append_player_action(
                    state.user_id,
                    state.chunk_id,
                    ActionToken.COLOR,
                    board,  
                )