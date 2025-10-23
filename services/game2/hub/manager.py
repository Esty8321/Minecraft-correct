from __future__ import annotations
import asyncio
import logging
import random
from typing import Tuple
from fastapi import WebSocket
import torch


from services.game2.data.db_chunks import save_chunk
from services.game2.core.bits import get_bit, make_color, set_bit, with_player
from services.game2.core.settings import BIT_HAS_LINK, DTYPE
# 
from services.game2.hub.scroll import ScrollService
from services.game2.hub.color import ColorService

from .types import MatrixPayload, MOVE_TOKENS
from .helper import extract_token, verify_token_or_reason
from ..data.db_history import ActionToken, append_player_action
from .sessions import SessionStore, PlayerSession
from .world import WorldService
from .movement import MovementService
from ..data.db_history import append_player_action
from .types import MOVE_TOKENS
# from .messaging import MessagingService
from services.game2.hub.scroll import ScrollService
from services.game2.hub.color import ColorService

from .helper import send_json

from .bot import BotService

logger = logging.getLogger(__name__)

class Hub:
    def __init__(self) -> None:
        self.sessions = SessionStore()
        self.world = WorldService()
        self.movement = MovementService(self.world)
        self.scroll = ScrollService(self.sessions, self.world)
        self.color  = ColorService(self.world, self.scroll)
        self.bots   = BotService(self.world, self.movement, self.scroll)
        self._global_lock = asyncio.Lock()
    
    

    async def connect(self, ws: WebSocket) -> None:
        token = extract_token(ws)
        ok, reason, user_id = verify_token_or_reason(token)
        if not ok or not user_id:
            await ws.close(code=4001)
            logger.debug(f"reject ws: {reason}")
            return
        
        
        if self.bots.is_running(user_id):
            bot_state = self.bots.stop(user_id)
        else:
            bot_state = None
            
            
        existing_sockets = self.sessions.sockets_for_user(user_id)
        
        if existing_sockets:
            any_ws = next(iter(existing_sockets))
            existing_session = self.sessions.get(any_ws)
            state = existing_session.state
            board = self.world.ensure_chunk(state.chunk_id)
            board[state.pos.row, state.pos.col] = state.visible_cell
        
        else:
            if bot_state is not None:
                state = bot_state
            else:
                chunk_id, spawn = await self.world.get_spawn_position(user_id)
                state = await self.world.spawn_player(user_id, chunk_id,spawn)
        self.sessions.add(ws, PlayerSession( state=state))
        await self.scroll.broadcast_chunk(state.chunk_id, self.world.ensure_chunk(state.chunk_id))

           
    
    # async def disconnect(self, ws: WebSocket) -> None:
    #     sess = self.sessions.pop(ws)
    #     if not sess:
    #         return
    #     user_id = sess.state.user_id
     
    #     await self.world.despawn_player(sess.state, user_id=sess.state.user_id)##check if I realy need it??

    #     if len(self.sessions.sockets_for_user(user_id)) == 0:
    #         self.bots.start(user_id, sess.state)
            
   
    # async def disconnect(self, ws: WebSocket) -> None:
    #     print("===in the disconnect function==")
    #     sess = self.sessions.pop(ws)
    #     if not sess:
    #         print("there is not sess==")
    #         return
        
    #     user_id = sess.state.user_id
    #     chunk_id = sess.state.chunk_id

    #     # Despawn the player visually (optional)
    #     await self.world.despawn_player(sess.state, user_id=user_id)
    #     print(f"Player {user_id} disconnected from {chunk_id}")

    #     # --- NEW: Check if the user has no more sockets ---
    #     remaining = self.sessions.sockets_for_user(user_id)
    #     print("the remaining is: ", remaining)
    #     if not remaining:
    #         # Start the bot to play instead
    #         print("I am the last here ==")
    #         if hasattr(self, "bots"):
    #             print("==Action the bot==")
    #             await self.bots.start(user_id, sess.state)
    #         else:
    #             print("No BotService attached to Hub")

    async def disconnect(self, ws: WebSocket) -> None:
         print("===in the disconnect function==")
         try:
             sess = self.sessions.pop(ws)
             if not sess:
                 print("there is not sess==")
                 return

             user_id = sess.state.user_id
             chunk_id = sess.state.chunk_id

             print("before despawn==")
             await self.world.despawn_player(sess.state)
             print(f"Player {user_id} disconnected from {chunk_id}")

             remaining = self.sessions.sockets_for_user(user_id)
             print("the remaining is: ", remaining)
             if not remaining:
                 print("I am the last here ==")
                 if hasattr(self, "bots"):
                     print("==Action the bot==")
                     self.bots.start(user_id, sess.state)
                 else:
                     print("No BotService attached to Hub")
         except Exception as e:
             import traceback
             print("❌ Error in disconnect:", e)
             traceback.print_exc()

    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        moved = await self.movement.apply_move(state, dr, dc)
        board = self.world.ensure_chunk(state.chunk_id)

        tok = MOVE_TOKENS.get((dr, dc))
        if tok:
           try:
                append_player_action(state.user_id, state.chunk_id, tok, board)
           except Exception as e:
                logger.warning("Failed to append player action for move: %s", e)

        
      

        if moved.old_chunk_id and moved.old_chunk_id != state.chunk_id:
         for s in self.sessions.sockets_for_user(state.user_id):
            self.sessions.detach_watcher(moved.old_chunk_id, s)
            self.sessions.attach_watcher(state.chunk_id, s)
         new_board = self.world.ensure_chunk(state.chunk_id)

         await self.scroll.broadcast_chunk(state.chunk_id, new_board)
         await self.scroll.maybe_send_message_at(ws, state)   # ← הוספנו כאן

         return
        await self.scroll.broadcast_chunk(state.chunk_id, board)
        await self.scroll.maybe_send_message_at(ws, state)

  
    async def write_message(self, ws: WebSocket, content: str) -> None:
        sess = self.sessions.get(ws)
        if not sess: 
          return
        await self.scroll.write_treasure_message(sess.state, content)

 

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
        
    async def color_plus_plus(self, ws: WebSocket) -> None:

        sess = self.sessions.get(ws)
        if not sess:
          return
        await self.color.color_plus_plus_state(sess.state)
        
        