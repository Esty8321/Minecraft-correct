# import random
# import torch
# from .world import WorldService
# from .scrolls import ScrollService
# <<<<<<< HEAD
# from ..core.settings import DTYPE, BIT_HAS_LINK
# from ..core.bits import make_color, get_bit, set_bit
# =======
# from ..core.settings import BIT_HAS_LINK_IDX, DTYPE, BIT_HAS_LINK_IDX
# from ..core.bits import get_player_color_by_user_id, get_player_color_by_user_id, make_color, get_bit,set_bit,with_player
# >>>>>>> c1df2ba2b4e8ec4156917f47171ebc6c8d71fff5
# from .types import PlayerState
# from ..data.db_history import ActionToken

# class ColorService:
#     """Handles player color changes and updates the board and database accordingly."""

#     def __init__(self, world: WorldService, scroll: ScrollService):
#         self.world = world
#         self.scroll = scroll
# <<<<<<< HEAD

#     def color_plus_plus(self, state: PlayerState) -> None:
#         """Randomize player's base color and update both visible and underlying cells."""
#         board = self.world.ensure_chunk(state.chunk_id)
#         r, g, b = (random.randint(0, 3) for _ in range(3))
#         new_base_color_val = int(make_color(r, g, b))
#         old_under_val = int(state.underlying_cell.item())

#         if get_bit(torch.tensor(old_under_val), BIT_HAS_LINK):
#             new_base_color_val = int(set_bit(torch.tensor(new_base_color_val), BIT_HAS_LINK, True))

#         state.underlying_cell = torch.tensor(new_base_color_val, dtype=DTYPE)
#         visible_val = new_base_color_val  # same, no player bit anymore

#         if get_bit(torch.tensor(new_base_color_val), BIT_HAS_LINK):
#             visible_val = int(set_bit(torch.tensor(visible_val), BIT_HAS_LINK, True))
    
#         board[state.pos.row, state.pos.col] = torch.tensor(visible_val, dtype=DTYPE)
#         self.world._mark_dirty(state.chunk_id)
# =======
        
        
#     # def color_plus_plus(self, state: PlayerState) -> None:
#     #     """Randomize player's base color and update both visible and underlying cells."""
#     #     board = self.world.ensure_chunk(state.chunk_id)
#     #     r, g, b = (random.randint(0, 3) for _ in range(3))
#     #     new_base_color_val = int(make_color(r, g, b))
#     #     old_under_val = int(state.underlying_cell.item()) 
       
#     #     if get_bit(old_under_val, BIT_HAS_LINK):
#     #         new_base_color_val = int(set_bit(new_base_color_val, BIT_HAS_LINK, True))
        
#     #     state.underlying_cell = torch.tensor(new_base_color_val, dtype=DTYPE)
#     #     visible_with_player_val = int(with_player(state.color))
       
#     #     if get_bit(new_base_color_val, BIT_HAS_LINK):
#     #         visible_with_player_val = int(set_bit(visible_with_player_val, BIT_HAS_LINK, True))

#     #     board[state.pos.row, state.pos.col] = torch.tensor(visible_with_player_val, dtype=DTYPE)
#     #     # self.world.chunk_db.save_chunk(state.chunk_id, board)
#     #     self.world._mark_dirty(state.chunk_id)
        
#     #     self.world.player_actions_history.append_player_action(
#     #                 state.user_id,
#     #                 state.chunk_id,
#     #                 ActionToken.COLOR,
#     #                 board,  
#     #             )


      
#     def color_plus_plus(self, state: PlayerState) -> None:
#         board = self.world.ensure_chunk(state.chunk_id)
#         r0, c0 = state.pos.row, state.pos.col

#         vis_val   = int(board[r0, c0].item())
#         under_val = int(state.underlying_cell.item())

#         def decode_code_from_under(v: int) -> int:
#             base = v
#             if get_bit(base, BIT_HAS_LINK_IDX):
#                 base = int(set_bit(base, BIT_HAS_LINK_IDX, False))
#             for cand in range(64):
#                 r = (cand >> 4) & 3
#                 g = (cand >> 2) & 3
#                 b = cand & 3
#                 if int(make_color(r, g, b)) == base:
#                     return cand
#             return 0

#         # 1) עדכוני under בלבד (המשבצת מתחת לשחקן)
#         old_code = decode_code_from_under(under_val)
#         new_code = (old_code + 1) % 64
#         r = (new_code >> 4) & 3
#         g = (new_code >> 2) & 3
#         b = new_code & 3

#         new_under = int(make_color(r, g, b))
#         if get_bit(under_val, BIT_HAS_LINK_IDX) or get_bit(vis_val, BIT_HAS_LINK_IDX):
#             new_under = int(set_bit(new_under, BIT_HAS_LINK_IDX, True))

#         # 2) צבע השחקן – תמיד קבוע לפי ה-ID (לא מפענחים מהתא!)
#         base_player_color = getattr(state, "player_color", get_player_color_by_user_id(state.user_id))
#         new_vis = int(with_player(base_player_color))

#         # 3) כתיבה ללוח ושמירה
#         state.underlying_cell = torch.tensor(new_under, dtype=DTYPE)
#         board[r0, c0] = torch.tensor(new_vis, dtype=DTYPE)

#         self.world._mark_dirty(state.chunk_id)
#         self.world.player_actions_history.append_player_action(
#             state.user_id, state.chunk_id, ActionToken.COLOR, board
#         )
# >>>>>>> c1df2ba2b4e8ec4156917f47171ebc6c8d71fff5
