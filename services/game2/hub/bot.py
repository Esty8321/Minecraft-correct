# services/game2/hub/bot.py
from __future__ import annotations
import asyncio
import torch
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from services.game2.models.bot_gru import GRUPolicy, HIDDEN_DIM
from services.game2.core.settings import W, H, DTYPE
from services.game2.hub.types import PlayerState
from services.game2.hub.movement import MovementService
from services.game2.hub.messaging import MessagingService
from services.game2.hub.world import WorldService
from services.game2.data.db_history import ActionToken
# מיפוי מרחב פלט (0..5) → טוקן בפועל (1..6)
IDX_TO_TOKEN = {i: i+1 for i in range(6)}
# מיפוי טוקן → (dr,dc)
MOVE_DIR = {
    ActionToken.RIGHT: (0, +1),
    ActionToken.LEFT:  (0, -1),
    ActionToken.UP:    (-1, 0),
    ActionToken.DOWN:  (+1, 0),
}

@dataclass
class BotCtx:
    user_id: str
    state: PlayerState
    task: asyncio.Task
    h: Optional[torch.Tensor] = None   # (1,1,128)
    last_token: int = 0                # 0 בתחילה = “אין פעולה קודמת”

class BotService:
    def __init__(self, world: WorldService, movement: MovementService, messaging: MessagingService):
        self.world = world
        self.movement = movement
        self.messaging = messaging
        self.model: Optional[GRUPolicy] = None
        self.user_vocab: Dict[str,int] = {}
        self.bots: Dict[str, BotCtx] = {}
        self.device = "cpu"
        

    def load_model(self, weights_path: str = "bot_gru.pt"):
        ckpt = torch.load(weights_path, map_location="cpu")
        self.user_vocab = ckpt["user_vocab"]
        self.model = GRUPolicy(num_users=len(self.user_vocab))
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    def _user_idx(self, user_id: str) -> int:
        # אם משתמש חדש שלא הופיע בטריינינג — למפות ל-0
        return self.user_vocab.get(user_id, 0)

    async def _tick(self, user_id: str):
        ctx = self.bots[user_id]
        # קצב צעדים — אפשר לכוון
        TICK = 0.30  # שניות
        while user_id in self.bots:
            state = ctx.state
            board = self.world.ensure_chunk(state.chunk_id)
            board_ = board.clone().to(torch.float32).unsqueeze(0).unsqueeze(0)  # (1,1,H,W)

            with torch.no_grad():
                logits, ctx.h = self.model.forward_step(
                    board_, ctx.last_token, self._user_idx(user_id), ctx.h
                )
                pred_idx = int(torch.argmax(logits, dim=1).item())   # 0..5
                token = IDX_TO_TOKEN[pred_idx]                        # 1..6

            # ביצוע פעולה
            if token in MOVE_DIR:
                dr, dc = MOVE_DIR[token]
                await self.movement.apply_move(state, dr, dc)
                await self.messaging.broadcast_player_move(user_id, None, state.chunk_id)
            elif token == ActionToken.COLOR:
                # “צבע++” — נשתמש בשירות קיים
                # אין לנו ws, לכן נעדכן ישירות דרך MessagingService/WorldService אם יש צורך
                # אפשר גם להוסיף פונקציה public לעשות color_plus_plus בלי ws (ראו Hub.color_plus_plus)
                await self.color_plus_plus(state)
            # DM (6) — נתעלם בבוט בסיסי

            ctx.last_token = token
            await asyncio.sleep(TICK)

    def start(self, user_id: str, state: PlayerState):
        if (self.model is None) or (not self.user_vocab):
            # טעינה עצלה
            self.load_model()
        if user_id in self.bots:
            self.stop(user_id)
        task = asyncio.create_task(self._tick(user_id))
        self.bots[user_id] = BotCtx(user_id=user_id, state=state, task=task)

    def stop(self, user_id: str) -> Optional[PlayerState]:
        ctx = self.bots.pop(user_id, None)
        if ctx:
            ctx.task.cancel()
            return ctx.state
        return None

    def is_running(self, user_id: str) -> bool:
        return user_id in self.bots



    async def color_plus_plus(self, state: PlayerState):
        """Perform color++ for a bot (change color, update board, broadcast)."""
        import random, torch
        from services.game2.core.bits import make_color, set_bit, get_bit, with_player
        from services.game2.core.settings import DTYPE, BIT_HAS_LINK
        from services.game2.data.db_chunks import save_chunk
        from services.game2.data.db_history import append_player_action, ActionToken

        board = self.world.ensure_chunk(state.chunk_id)

        # Choose random new color
        r, g, b = (random.randint(0, 3) for _ in range(3))
        new_base_color_val = int(make_color(r, g, b))

        old_under_val = int(state.underlying_cell.item())

        # Keep “link” bit if there’s a message/treasure under
        if get_bit(old_under_val, BIT_HAS_LINK):
            new_base_color_val = int(set_bit(new_base_color_val, BIT_HAS_LINK, True))

        # Update underlying cell
        state.underlying_cell = torch.tensor(new_base_color_val, dtype=DTYPE)

        # Compose visible cell (player + color)
        visible_with_player_val = int(with_player(state.color))
        if get_bit(new_base_color_val, BIT_HAS_LINK):
            visible_with_player_val = int(set_bit(visible_with_player_val, BIT_HAS_LINK, True))

        board[state.pos.row, state.pos.col] = torch.tensor(visible_with_player_val, dtype=DTYPE)
        save_chunk(state.chunk_id, board)

        # Log in history
        try:
            append_player_action(
                state.user_id,
                state.chunk_id,
                ActionToken.COLOR,
                board,
            )
        except Exception:
            pass

        # Broadcast to all watchers of this chunk
        await self.messaging.broadcast_chunk(state.chunk_id)
