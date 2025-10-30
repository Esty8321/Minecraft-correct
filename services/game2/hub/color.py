import random
import torch
from .world import WorldService
from .scrolls import ScrollService
from ..core.settings import DTYPE
from ..core.bits import make_color, get_bit, set_bit

from ..core.settings import BIT_HAS_LINK_IDX, DTYPE, BIT_HAS_LINK_IDX
from ..core.bits import get_player_color_by_user_id, get_player_color_by_user_id, make_color, get_bit,set_bit,with_player
from .types import PlayerState
from ..data.db_history import ActionToken

class ColorService:
    """Handles player color changes and updates the board and database accordingly."""

    def __init__(self, world: WorldService, scroll: ScrollService):
        self.world = world
        self.scroll = scroll
    
    def color_plus_plus(self, state: PlayerState) -> None:
        board = self.world.ensure_chunk(state.chunk_id)
        r0, c0 = state.pos.row, state.pos.col

        vis_val   = int(board[r0, c0].item())
        under_val = int(state.underlying_cell.item())

        def _has_link(v: int) -> bool:
            return get_bit(v, BIT_HAS_LINK_IDX)

        def _set_link(v: int, on: bool = True) -> int:
            return int(set_bit(v, BIT_HAS_LINK_IDX, on))

        def _decode_code_from_under(v: int) -> int:
            base = v
            if _has_link(base):
                base = _set_link(base, False)
            for cand in range(64):
                rr = (cand >> 4) & 3
                gg = (cand >> 2) & 3
                bb = cand & 3
                if int(make_color(rr, gg, bb)) == base:
                    return cand
            return 0

        old_code = _decode_code_from_under(under_val)
        new_code = (old_code + 1) % 64
        r = (new_code >> 4) & 3
        g = (new_code >> 2) & 3
        b =  new_code        & 3

        new_base = int(make_color(r, g, b))

        if _has_link(under_val) or _has_link(vis_val):
            new_base = _set_link(new_base, True)

        state.underlying_cell = torch.tensor(new_base, dtype=DTYPE)
        board[r0, c0]         = torch.tensor(new_base, dtype=DTYPE)

     
        self.world._mark_dirty(state.chunk_id)
       