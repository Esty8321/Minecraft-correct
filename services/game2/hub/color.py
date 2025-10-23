from __future__ import annotations
from asyncio.log import logger
import random
import torch

from services.game2.core.bits import make_color, set_bit, get_bit, with_player
from services.game2.core.settings import DTYPE, BIT_HAS_LINK
from services.game2.data.db_chunks import save_chunk
from services.game2.data.db_history import append_player_action, ActionToken
from services.game2.hub.types import PlayerState
from services.game2.hub.scroll import ScrollService  
from services.game2.hub.world import WorldService
class ColorService:
    def __init__(self, world: WorldService, scroll: ScrollService):
       self.world = world
       self.scroll = scroll

    async def color_plus_plus_state(self, state: PlayerState) -> None:
        
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
        save_chunk(state.chunk_id, board)

        try:
            append_player_action(state.user_id, state.chunk_id, ActionToken.COLOR, board)
        except Exception as e:
              logger.warning("Failed to append player color action: %s", e)

        await self.scroll.broadcast_chunk(state.chunk_id, board)
