
from __future__ import annotations
import asyncio
import torch
from typing import Dict, Optional
from dataclasses import dataclass

from services.game2.models.bot_gru import GRUPolicy
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
    """Holds per-bot runtime context, including hidden state and async task."""
    user_id: str
    state: PlayerState
    task: asyncio.Task
    h: Optional[torch.Tensor] = None   # (1,1,128)
    last_token: int = 0                

class BotService:
    """Coordinates loading of the GRU model, starts/stops bots, and performs periodic action ticks."""
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
        TICK = 0.30
        while user_id in self.bots:
            try:
                state = ctx.state
                board = self.world.ensure_chunk(state.chunk_id)
                board_ = board.clone().to(torch.float32).unsqueeze(0).unsqueeze(0)
    
                with torch.no_grad():
                    logits, ctx.h = self.model.forward_step(
                        board_, ctx.last_token, self._user_idx(user_id), ctx.h
                    )
                    pred_idx = int(torch.argmax(logits, dim=1).item())
                    token = IDX_TO_TOKEN[pred_idx]
    
                if token in MOVE_DIR:
                    dr, dc = MOVE_DIR[token]
                    await self.movement.apply_move(state, dr, dc)
                    await self.scroll.broadcast_chunk( state.chunk_id)
                elif token == ActionToken.COLOR:
                    await self.color.color_plus_plus(state)
                elif token == ActionToken.DM:
                    ##here we need to pass for the model of Shira this user_id with the closet_user_id and get correct message
                    pass#implement it after
    
                ctx.last_token = token
                await asyncio.sleep(TICK)
            except Exception as e:
                import traceback
                traceback.print_exc()
                break
            
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
