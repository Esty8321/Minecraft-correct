

from __future__ import annotations
import asyncio
from collections import deque
from pathlib import Path
from typing import Dict, Optional
import torch

from services.game2.models.bot_gru_v2 import GRUPolicyV2, MAX_SEQ
from services.game2.hub.types import PlayerState, ActionToken
from services.game2.hub.movement import MovementService
from services.game2.hub.world import WorldService
from services.game2.hub.scrolls import ScrollService
from services.game2.hub.color import ColorService
from services.game2.core.settings import H, W

MOVE_DIR = {
    ActionToken.RIGHT: (0, +1),
    ActionToken.LEFT:  (0, -1),
    ActionToken.UP:    (-1, 0),
    ActionToken.DOWN:  (+1, 0),
}

class BotCtx:
    def __init__(self, user_id: str, state: PlayerState):
        self.user_id = user_id
        self.state = state
        self.task: Optional[asyncio.Task] = None
        self.last_actions: deque[int] = deque(maxlen=MAX_SEQ)

class BotService:
    def __init__(self, world: WorldService, movement: MovementService,
                 scroll: ScrollService, color_service: ColorService,
                 models_root: Path = Path("models/users")):

        self.world = world
        self.movement = movement
        self.scroll = scroll
        self.color = color_service
        self.models_root = models_root
        self.model_cache: Dict[str, GRUPolicyV2] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.bots: Dict[str, BotCtx] = {}

    def _weights_path(self, user_id: str) -> Path:
        return self.models_root / user_id / "gru_policy.pt"

    def _load_model_for_user(self, user_id: str) -> GRUPolicyV2:
        if user_id in self.model_cache:
            return self.model_cache[user_id]

        p = self._weights_path(user_id)
        model = GRUPolicyV2(board_h=H, board_w=W).to(self.device)

        if p.exists():
            ckpt = torch.load(p, map_location="cpu")
            model.load_state_dict(ckpt["state_dict"])

        model.eval()
        self.model_cache[user_id] = model
        return model

    async def _tick(self, user_id: str):
        ctx = self.bots[user_id]
        model = self._load_model_for_user(user_id)
        TICK = 0.25

        while user_id in self.bots:
            try:
                seq = list(ctx.last_actions)
                pad = [0] * (MAX_SEQ - len(seq))
                seq_tensor = torch.tensor([pad + seq], dtype=torch.long, device=self.device)

                row = torch.tensor([ctx.state.pos.row], device=self.device)
                col = torch.tensor([ctx.state.pos.col], device=self.device)

                with torch.no_grad():
                    logits = model(seq_tensor, row, col)
                    pred = int(torch.argmax(logits, dim=1).item()) + 1

                token = ActionToken(pred)

                if token in MOVE_DIR:
                    dr, dc = MOVE_DIR[token]
                    await self.movement.apply_move(ctx.state, dr, dc)
                    await self.scroll.broadcast_chunk(ctx.state.chunk_id)

                elif token == ActionToken.COLOR:
                    self.color.color_plus_plus(ctx.state)
                    await self.scroll.broadcast_chunk(ctx.state.chunk_id)

                ctx.last_actions.append(pred)
                await asyncio.sleep(TICK)

            except Exception:
                import traceback
                traceback.print_exc()
                break

    def start(self, user_id: str, state: PlayerState):
        if user_id in self.bots:
            self.stop(user_id)

        ctx = BotCtx(user_id=user_id, state=state)
        self.bots[user_id] = ctx
        ctx.task = asyncio.create_task(self._tick(user_id))

        print(f"[BOT V2] started for {user_id}")

    def stop(self, user_id: str):
        ctx = self.bots.pop(user_id, None)
        if ctx and ctx.task:
            ctx.task.cancel()
        print(f"[BOT V2] stopped for {user_id}")

    def is_running(self, user_id: str) -> bool:
        return user_id in self.bots
