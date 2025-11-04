from __future__ import annotations
import asyncio
import time
import torch
from typing import Dict, Optional, NamedTuple
from dataclasses import dataclass

from services.game2.models.bot_gru import GRUPolicy
from services.game2.hub.types import PlayerState
from services.game2.hub.movement import MovementService
from services.game2.hub.scrolls import ScrollService
from services.game2.hub.world import WorldService
from services.game2.data.db_history import ActionToken
from services.game2.hub.color import ColorService
from services.game2.core.settings import W, H

IDX_TO_TOKEN = {i: i + 1 for i in range(7)}
SLEEP_TOKEN = 7
SLEEP_IDX = SLEEP_TOKEN - 1
MAX_GAP_SEC = 30.0
INFER_TEMPERATURE = 1.3
INFER_EPSILON = 0.05

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
    task: asyncio.Task | None
    h: Optional[torch.Tensor] = None
    last_token: int = 0
    last_ts: float = 0.0

class BotSnapshot(NamedTuple):
    state: PlayerState
    last_token: int
    last_ts: float

class BotService:
    def __init__(self, world: WorldService, movement: MovementService,
                 scroll: ScrollService, color_service: ColorService):
        self.world = world
        self.movement = movement
        self.scroll = scroll
        self.model: Optional[GRUPolicy] = None
        self.user_vocab: Dict[str, int] = {}
        self.bots: Dict[str, BotCtx] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.color = color_service

    def load_model(self, weights_path: str = "bot_gru.pt"):
        try:
            ckpt = torch.load(weights_path, map_location="cpu")
        except Exception:
            raise RuntimeError(f"Model weights not found at {weights_path}")

        self.user_vocab = ckpt["user_vocab"]
        self.model = GRUPolicy(num_users=len(self.user_vocab)).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        print(f"[BOT] Loaded GRU model ({len(self.user_vocab)} users).")

    def _user_idx(self, user_id: str) -> int:
        return self.user_vocab.get(user_id, 0)

    def _get_players_in_chunk(self, chunk_id: str):
        cp = getattr(self.movement, "chunk_players", None) or getattr(self.world, "chunk_players", None)
        if cp is None:
            return []
        return cp.get_players_in_chunk(chunk_id)

    def _build_occ_map(self, state: PlayerState) -> torch.Tensor:
        occ = torch.zeros((H, W), dtype=torch.uint8)
        players = self._get_players_in_chunk(state.chunk_id)
        me = getattr(state, "user_id", None)
        for p in players:
            pid = p.get("id")
            r = int(p.get("row", -1))
            c = int(p.get("col", -1))
            if pid and pid != me and 0 <= r < H and 0 <= c < W:
                occ[r, c] = 255
        return occ

    def _extract_rc(self, state: PlayerState):
        for a, b in (("row", "col"), ("r", "c")):
            if hasattr(state, a) and hasattr(state, b):
                return int(getattr(state, a)), int(getattr(state, b))
        return None

    def _mask_blocked_move(self, logits: torch.Tensor, token: int,
                           state: PlayerState, occ: torch.Tensor) -> int:
        if token not in MOVE_DIR:
            return token
        rc = self._extract_rc(state)
        if rc is None:
            return token
        r, c = rc
        dr, dc = MOVE_DIR[token]
        r2, c2 = r + dr, c + dc
        if not (0 <= r2 < H and 0 <= c2 < W) or occ[r2, c2] != 0:
            masked = logits.clone()
            masked[0, token - 1] = -1e9
            new_idx = int(torch.argmax(masked, dim=1).item())
            return IDX_TO_TOKEN[new_idx]
        return token

    async def predict_action(self, ctx: BotCtx) -> tuple[int, float, torch.Tensor]:
        state = ctx.state
        board = self.world.ensure_chunk(state.chunk_id).to(torch.uint8)
        occ = self._build_occ_map(state)
        board_2ch = torch.stack([board, occ], dim=0).unsqueeze(0).to(self.device)

        now = time.time()
        prev_gap = now - (ctx.last_ts or now)
        prev_delta_norm = min(max(prev_gap / MAX_GAP_SEC, 0.0), 1.0)

        with torch.no_grad():
            logits, h_new, sleep_reg = self.model.forward_step(
                board_2ch,
                ctx.last_token,
                self._user_idx(ctx.user_id),
                prev_delta_norm,
                ctx.h,
            )
            temp_logits = logits / INFER_TEMPERATURE
            probs = torch.softmax(temp_logits, dim=1)[0]
            if torch.rand(()) < INFER_EPSILON:
                pred_idx = torch.multinomial(probs, num_samples=1).item()
            else:
                pred_idx = int(torch.argmax(probs, dim=0).item())
            token = IDX_TO_TOKEN[pred_idx]
            sleep_norm = float(sleep_reg.item())
            sleep_sec = max(0.5, min(sleep_norm * MAX_GAP_SEC, 10.0))
            print(f"[BOT DEBUG] {ctx.user_id} probs={probs.cpu().numpy().round(3)} "
                  f"pred_token={token} prev_gap={prev_gap:.2f}s prev_delta_norm={prev_delta_norm:.2f}")
        token = self._mask_blocked_move(logits, token, state, occ)
        return token, sleep_sec, h_new

    async def _tick(self, user_id: str):
        ctx = self.bots[user_id]
        TICK = 0.30
        while user_id in self.bots:
            try:
                token, sleep_sec, h_new = await self.predict_action(ctx)
                ctx.h = h_new
                state = ctx.state
                if token in MOVE_DIR:
                    dr, dc = MOVE_DIR[token]
                    print(f"[BOT] move {token} → ({dr},{dc})")
                    result = await self.movement.apply_move(state, dr, dc)
                    if isinstance(result, PlayerState):
                        ctx.state = result
                    elif hasattr(result, "new_state"):
                        ctx.state = result.new_state
                    await self.scroll.broadcast_chunk(ctx.state.chunk_id)
                elif token == ActionToken.COLOR:
                    print("[BOT] color++")
                    self.color.color_plus_plus(state)
                    await self.scroll.broadcast_chunk(state.chunk_id)
                elif token == ActionToken.DM:
                    print("[BOT] chat/DM (noop)")
                elif token == SLEEP_TOKEN:
                    print(f"[BOT] sleep for {sleep_sec:.2f}s")
                    await asyncio.sleep(sleep_sec)
                ctx.last_token = int(token)
                ctx.last_ts = time.time()
                await asyncio.sleep(TICK)
            except Exception:
                import traceback
                traceback.print_exc()
                break

    def start(self, user_id: str, state: PlayerState,
              h: Optional[torch.Tensor] = None,
              last_token: int = 0,
              last_ts: float = 0.0):
        if (self.model is None) or (not self.user_vocab):
            self.load_model()
        if user_id in self.bots:
            self.stop(user_id)
        ctx = BotCtx(user_id=user_id, state=state, task=None,
                     h=h, last_token=last_token, last_ts=last_ts or time.time())
        self.bots[user_id] = ctx
        ctx.task = asyncio.create_task(self._tick(user_id))
        print(f"[BOT] started for {user_id}")

    def stop(self, user_id: str) -> Optional[BotSnapshot]:
        ctx = self.bots.pop(user_id, None)
        if ctx:
            if ctx.task:
                ctx.task.cancel()
            print(f"[BOT] stopped for {user_id}")
            return BotSnapshot(state=ctx.state, last_token=ctx.last_token, last_ts=ctx.last_ts)
        return None

    def is_running(self, user_id: str) -> bool:
        return user_id in self.bots
