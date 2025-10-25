#V
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
from services.game2.hub.scrolls import  ScrollService
from services.game2.hub.world import WorldService
from services.game2.data.db_history import ActionToken
from .color import ColorService

IDX_TO_TOKEN = {i: i+1 for i in range(6)}

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
    last_token: int = 0                

class BotService:
    def __init__(self, world: WorldService, movement: MovementService, scroll: ScrollService, color_service :ColorService):
        self.world = world
        self.movement = movement
        self.scroll = scroll
        self.model: Optional[GRUPolicy] = None
        self.user_vocab: Dict[str,int] = {}
        self.bots: Dict[str, BotCtx] = {}
        self.device = "cpu"
        self.color = color_service
        
        print("== in init the bot ==")

    def load_model(self, weights_path: str = "bot_gru.pt"):
        try:
             ckpt = torch.load(weights_path, map_location="cpu")
        except:
             raise RuntimeError(f"Model weights not found at {weights_path}")
     
        self.user_vocab = ckpt["user_vocab"]
        self.model = GRUPolicy(num_users=len(self.user_vocab))
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    def _user_idx(self, user_id: str) -> int:    
        return self.user_vocab.get(user_id, 0)

    async def _tick(self, user_id: str):
        ctx = self.bots[user_id]
        # קצב צעדים — אפשר לכוון
        TICK = 0.3  # שניות
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
           
            if token in MOVE_DIR:
                dr, dc = MOVE_DIR[token]
                old_chunk = state.chunk_id
                await self.movement.apply_move(state, dr, dc)

                # Notify current chunk
                await self.scroll.broadcast_player_move(user_id, None, state.chunk_id)
  
                # ✅ NEW: if bot moved to a different chunk — broadcast new chunk board
                if state.chunk_id != old_chunk:
                    print(f"[BOT] {user_id} moved from {old_chunk} → {state.chunk_id}")
                    # force the world to ensure/load this chunk
                    new_board = self.world.ensure_chunk(state.chunk_id)
                    # broadcast the full chunk board
                    await self.scroll.broadcast_chunk(state.chunk_id, new_board)

           
            elif token == ActionToken.COLOR:
                # “צבע++” — נשתמש בשירות קיים
                # אין לנו ws, לכן נעדכן ישירות דרך MessagingService/WorldService אם יש צורך
                # אפשר גם להוסיף פונקציה public לעשות color_plus_plus בלי ws (ראו Hub.color_plus_plus)
                await self.color.color_plus_plus(state)
                await self.scroll.broadcast_chunk(state.chunk_id)
            # DM (6) — נתעלם בבוט בסיסי

            ctx.last_token = token
            await asyncio.sleep(TICK)

    def start(self, user_id: str, state: PlayerState):
        if (self.model is None) or (not self.user_vocab):
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
