from __future__ import annotations
import asyncio
import logging
import random
from typing import Tuple


from fastapi import WebSocket
import torch

from services.game.bits import get_bit, inc_color, with_player
from services.game.db import save_chunk
from services.game.settings import BIT_HAS_LINK
from services.game2.core.bits import make_color, set_bit
from services.game2.core.settings import DTYPE


from .types import MatrixPayload, Coord, PlayerState, MOVE_TOKENS,Direction
from .helper import extract_token, verify_token_or_reason
from ..data.db_history import ActionToken, append_player_action
from .sessions import SessionStore, PlayerSession
from .world import WorldService
from .movement import MovementService
from .messaging import MessagingService
from .helper import send_json


logger = logging.getLogger(__name__)

class Hub:
    def __init__(self) -> None:
        # services
        self.sessions = SessionStore()
        self.world = WorldService()
        self.movement = MovementService(self.world)
        self.messaging = MessagingService(self.world, self.sessions)
        # global lock only for rare cross-service critical sections
        self._global_lock = asyncio.Lock()
    
   
    async def color_plus_plus(self, ws: WebSocket) -> None:

        sess = self.sessions.get(ws)
        if not sess:
            return

        state = sess.state
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
                append_player_action(
                    sess.user_id,
                    state.chunk_id,
                    ActionToken.COLOR,
                    board,  
                )
        except Exception:
                pass

        await self.messaging.broadcast_chunk(state.chunk_id)
    

     

    # --- connection lifecycle ---

    async def connect(self, ws: WebSocket) -> None:
        token = extract_token(ws)
        ok, reason, user_id = verify_token_or_reason(token)
        if not ok or not user_id:
            await ws.close(code=4001)
            logger.debug(f"reject ws: {reason}")
            return
        chunk_id, spawn = await self.world.get_spawn_position(user_id)
        state = await self.world.spawn_player(user_id, chunk_id, spawn)
        self.sessions.add(ws, PlayerSession(user_id=user_id, state=state))
        await self.messaging.broadcast_chunk(chunk_id)
        logger.info(f"Player {user_id} connected at {chunk_id}:{spawn.row},{spawn.col}")

    async def disconnect(self, ws: WebSocket) -> None:
        sess = self.sessions.pop(ws)
        if not sess:
         return
        await self.world.despawn_player(sess.state, user_id=sess.user_id)
        logger.info(f"Player {sess.user_id} disconnected from {sess.state.chunk_id}")
    
    # --- commands ---
    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        moved = await self.movement.apply_move(state, dr, dc)
        board = self.world.ensure_chunk(state.chunk_id)

        # record action token (non-blocking)
        token = MOVE_TOKENS.get((dr, dc))
        if token is not None:
            try:
                append_player_action(sess.user_id, state.chunk_id, token, board)

            except Exception:
                pass        
        if moved.old_chunk_id and moved.old_chunk_id != state.chunk_id:
            # remove from old watchers
            self.sessions.detach_watcher(moved.old_chunk_id, ws)
            # attach to new watchers
            self.sessions.attach_watcher(state.chunk_id, ws)
            # send the new chunk’s matrix to this player
            await self.messaging.broadcast_chunk(state.chunk_id)
            await self.messaging.maybe_send_message_at(ws)

            return
        # fanout updates
        
        await self.messaging.broadcast_chunk(state.chunk_id)
        await self.messaging.maybe_send_message_at(ws)

    async def write_message(self, ws: WebSocket, content: str) -> None:
      await self.messaging.write_message(ws, content)


    async def whereami(self, ws: WebSocket) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        board = self.world.ensure_chunk(sess.state.chunk_id)
        payload: MatrixPayload = {
            "type": "matrix",
            "w": board.shape[1],
            "h": board.shape[0],
            "data": board.flatten().tolist(),
            "chunk_id": sess.state.chunk_id,
            "total_players": self.sessions.player_count(),
            }
        await send_json(ws, payload)