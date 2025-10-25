#V
from __future__ import annotations
import asyncio
import logging
import random
from typing import Tuple
from fastapi import WebSocket
import torch

from services.game.bits import get_bit, with_player
from services.game.db import save_chunk
from services.game.settings import BIT_HAS_LINK
from services.game2.core.bits import make_color, set_bit
from services.game2.core.settings import DTYPE
from .types import MatrixPayload, MOVE_TOKENS

from .auth_utils import AuthUtils
from ..data.db_history import ActionToken, PlayerActionHistory##??change it be in class, and get the db from the main
from .sessions import SessionStore, PlayerSession
from .world import WorldService
from .movement import MovementService
from .scrolls import ScrollMessage
from .ws_utils import WebSocketUtils
from .scrolls import ScrollService
from .bot import BotService
from .color import ColorService
from ..core.settings import W, H

logger = logging.getLogger(__name__)
class Hub:
    def __init__(self, world: WorldService, movement: MovementService, 
                 scrolls: ScrollService, bots: BotService, sessions: SessionStore, color_service:ColorService) -> None:
        self.world = world
        self.movement = movement
        self.scrolls = scrolls
        self.bots = bots
        self.sessions = sessions
        self.color_service = color_service
        
        self._global_lock = asyncio.Lock()
               
    async def connect(self, ws: WebSocket) -> None:
        token = AuthUtils.extract_token(ws)
        ok, reason, user_id = AuthUtils.verify_token_or_reason(token)
        if not ok or not user_id:
            await ws.close(code=4001)
            logger.debug(f"reject ws: {reason}")
            return
        
        if self.bots.is_running(user_id):
            bot_state = self.bots.stop(user_id)
        else:
            bot_state = None    
        
        user_sockets = self.sessions.sockets_for_user(user_id)
        if user_sockets:
            any_ws = next(iter(user_sockets))
            existing_session = self.sessions.get(any_ws)
            state = existing_session.state
        else:
            if bot_state is not None:
                state = bot_state
            else:
                chunk_id, spawn = await self.world.get_spawn_position(user_id)
                state = await self.world.spawn_player(user_id, chunk_id,spawn)
        
        self.sessions.add(ws, PlayerSession( state=state))
        if not user_sockets:
            await self.scrolls.broadcast_chunk(state.chunk_id)

    async def disconnect(self, ws: WebSocket) -> None:
         try:
             sess = self.sessions.pop(ws)
             if not sess:
                 return

             user_id = sess.state.user_id
             chunk_id = sess.state.chunk_id
            #  await self.world.despawn_player(sess.state)##??realy don't need this - this save the position of the player, the last position but I already save them at the move command
            #??but that we don't need keep every time the user do move his last position mabye I can do it only when he do the disconnect
            ##??why didn't I delete this ws from the session_store?             
             remaining = self.sessions.sockets_for_user(user_id)
             if not remaining:   
                    self.bots.start(user_id, sess.state)
         except Exception as e:
             import traceback
             traceback.print_exc()

    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        moved = await self.movement.apply_move(state, dr, dc)
        board = self.world.ensure_chunk(state.chunk_id)
        await self.world.player_actions_history.record_player_action(state.user_id, state.chunk_id,dr,dc,board)##??how can I fix it??
              
        if moved.old_chunk_id and moved.old_chunk_id != state.chunk_id:
            self.sessions.update_watchers_after_chunk_change(state.user_id, moved.old_chunk_id, state.chunk_id)
            await self.scrolls.broadcast_chunk(state.chunk_id)
              
        else:
            await self.scrolls.broadcast_chunk(state.chunk_id)
        
        # await self.scrolls.broadcast_player_move(state.user_id,ws,  state.chunk_id)
  
    async def write_scroll(self, ws: WebSocket, content: str) -> None:
      await self.scrolls.write_scroll(ws, content)
 

    async def whereami(self, ws: WebSocket) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        board = self.world.ensure_chunk(sess.state.chunk_id)
        payload: MatrixPayload = {
            "type": "matrix",   
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": sess.state.chunk_id,
            "total_players": self.sessions.player_count(),
            }
        await WebSocket.send_json(ws, payload)
               
    async def color_plus_plus(self, ws: WebSocket) ->None:
        sess = self.sessions.get(ws)
        if not sess:
            return 
        self.color_service.color_plus_plus(sess.state)
        await self.scrolls.broadcast_chunk(sess.state.chunk_id)