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

      
    # def color_plus_plus(self, state: PlayerState) -> None:
    #     board = self.world.ensure_chunk(state.chunk_id)
    #     r0, c0 = state.pos.row, state.pos.col

    #     vis_val   = int(board[r0, c0].item())
    #     under_val = int(state.underlying_cell.item())

    #     def decode_code_from_under(v: int) -> int:
    #         base = v
    #         if get_bit(base, BIT_HAS_LINK_IDX):
    #             base = int(set_bit(base, BIT_HAS_LINK_IDX, False))
    #         for cand in range(64):
    #             r = (cand >> 4) & 3
    #             g = (cand >> 2) & 3
    #             b = cand & 3
    #             if int(make_color(r, g, b)) == base:
    #                 return cand
    #         return 0

    #     # 1) עדכוני under בלבד (המשבצת מתחת לשחקן)
    #     old_code = decode_code_from_under(under_val)
    #     new_code = (old_code + 1) % 64
    #     r = (new_code >> 4) & 3
    #     g = (new_code >> 2) & 3
    #     b = new_code & 3

    #     new_under = int(make_color(r, g, b))
    #     if get_bit(under_val, BIT_HAS_LINK_IDX) or get_bit(vis_val, BIT_HAS_LINK_IDX):
    #         new_under = int(set_bit(new_under, BIT_HAS_LINK_IDX, True))

    #     # 2) צבע השחקן – תמיד קבוע לפי ה-ID (לא מפענחים מהתא!)
    #     base_player_color = getattr(state, "player_color", get_player_color_by_user_id(state.user_id))
    #     new_vis = int(with_player(base_player_color))

    #     # 3) כתיבה ללוח ושמירה
    #     state.underlying_cell = torch.tensor(new_under, dtype=DTYPE)
    #     board[r0, c0] = torch.tensor(new_vis, dtype=DTYPE)

    #     self.world._mark_dirty(state.chunk_id)
    #     self.world.player_actions_history.append_player_action(
    #         state.user_id, state.chunk_id, ActionToken.COLOR, board
    #     )
    
    
    
    def color_plus_plus(self, state: PlayerState) -> None:
        board = self.world.ensure_chunk(state.chunk_id)
        r0, c0 = state.pos.row, state.pos.col

        vis_val   = int(board[r0, c0].item())
        under_val = int(state.underlying_cell.item())

        # ---- helpers ----
        def _has_link(v: int) -> bool:
            # אם אצלך get_bit מצפה ל-tensor, החליפי ל: get_bit(torch.tensor(v), BIT_HAS_LINK_IDX)
            return get_bit(v, BIT_HAS_LINK_IDX)

        def _set_link(v: int, on: bool = True) -> int:
            # אם אצלך set_bit מצפה ל-tensor, החליפי ל: int(set_bit(torch.tensor(v), BIT_HAS_LINK_IDX, on))
            return int(set_bit(v, BIT_HAS_LINK_IDX, on))

        def _decode_code_from_under(v: int) -> int:
            """שליפה של קוד 6-ביט מהתא שמתחת לשחקן, תוך הסרת ביט ה-LINK לצורך התאמה."""
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

        # ---- compute next color code (+1 mod 64) ----
        old_code = _decode_code_from_under(under_val)
        new_code = (old_code + 1) % 64
        r = (new_code >> 4) & 3
        g = (new_code >> 2) & 3
        b =  new_code        & 3

        new_base = int(make_color(r, g, b))

        # preserve LINK bit if it existed on visible/underlying
        if _has_link(under_val) or _has_link(vis_val):
            new_base = _set_link(new_base, True)

        # ---- write back (כמו בפונקציה הראשונה): visible == underlying == base ----
        state.underlying_cell = torch.tensor(new_base, dtype=DTYPE)
        board[r0, c0]         = torch.tensor(new_base, dtype=DTYPE)

     
        self.world._mark_dirty(state.chunk_id)
       
        # try:
        #     # התאם לנתיב ההיסטוריה אצלך (self.history / self.world.player_actions_history / פונקציה חופשית)
        #     self.world.player_actions_history.append_player_action(
        #         state.user_id, state.chunk_id, ActionToken.COLOR, board
        #     )
        # except Exception:
        #     pass