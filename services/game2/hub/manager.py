from __future__ import annotations
import asyncio
import logging
from fastapi import WebSocket
from .types import MatrixPayload
from .auth_utils import AuthUtils
from .sessions import SessionStore, PlayerSession
from .world import WorldService
from .scrolls import ScrollService
from .bot import BotService
from .color import ColorService
from .types import ActionToken
from ..core.settings import W, H
from ..data.db_players import PlayerDB
from ..data.user_logs import UserActionLogger

from .chunk_players import ChunkPlayers
logger = logging.getLogger(__name__)
class Hub:
    """Main orchestration hub connecting all services.
    Manages player connections, movements, scroll actions, color changes, and bot lifecycle."""

    def __init__(self, world: WorldService, movement,#movement service 
                 scrolls: ScrollService, bots: BotService, sessions: SessionStore, 
                 color_service:ColorService, players_db: PlayerDB, chunk_players: ChunkPlayers,
                 user_logger: UserActionLogger) -> None:
        from .movement import MovementService

        self.world = world
        self.movement: MovementService = movement
        self.scrolls = scrolls
        self.bots = bots   
        self.sessions = sessions
        self.color_service = color_service
        
        self.players_db = players_db
        self.chunk_players = chunk_players
        self._global_lock = asyncio.Lock()
        self.user_logger = user_logger
               
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
                state = bot_state.state##??see why need I chagne it like this
            else:
                chunk_id, spawn = await self.world.get_spawn_position(user_id)
                state = await self.world.spawn_player(user_id, chunk_id,spawn)

                self.chunk_players.add_player(chunk_id, user_id, spawn.row, spawn.col)
        self.sessions.add(ws, PlayerSession( state=state))
        await self.scrolls.broadcast_chunk(state.chunk_id)

   
    async def disconnect(self, ws: WebSocket) -> None:
         try:
             sess = self.sessions.pop(ws)
             if not sess:
                 return   

             user_id = sess.state.user_id             
             remaining = self.sessions.sockets_for_user(user_id)
            
             if not remaining:  
                 self.world.despawn_player(sess.state) 
                 self.bots.start(user_id, sess.state)
                 print("start the bot")
         except Exception as e:
             import traceback
             traceback.print_exc()


    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        # board_before = self.world.ensure_chunk(state.chunk_id).clone()
        # players_before = self.chunk_players.get_players_in_chunk(state.chunk_id)
        
        # self.world.player_actions_history.record_player_action(state.user_id, 
                                                            #    state.chunk_id, dr, dc, board_before, players= players_before)
        
        
        moved = await self.movement.apply_move(state, dr, dc)
        if moved.old_chunk_id and moved.old_chunk_id != state.chunk_id:
            self.sessions.update_watchers_after_chunk_change(state.user_id, moved.old_chunk_id, state.chunk_id)
            await self.scrolls.broadcast_chunk(state.chunk_id)
            await self.scrolls.broadcast_chunk(moved.old_chunk_id)
        else:
            await self.scrolls.broadcast_chunk(state.chunk_id)
        await self.scrolls.maybe_send_scroll_at(ws)
        
        move_map = {
            (0, 1):1,
            (0,-1):2,
            (-1, 0): 3,
            (1,0): 4
        }
        token = move_map.get((dr, dc))
        if token:
            self.user_logger.append(
                user_id=state.user_id,
                chunk_id=state.chunk_id,
                row = state.pos.row,
                col = state.pos.col,
                token=token,
            )
        
    async def write_scroll(self, ws: WebSocket, content: str) -> None:
      sess = self.sessions.get(ws)
      if not sess:
          return
      await self.scrolls.write_scroll(ws, content)
    
    
    async def whereami(self, ws: WebSocket) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        board = self.world.ensure_chunk(sess.state.chunk_id)
        players = self.chunk_players.get_players_in_chunk(sess.state.chunk_id)

        payload: MatrixPayload = {
            "type": "matrix",   
            "w": W,   
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": sess.state.chunk_id,
            "total_players": self.sessions.player_count(),
            "players": players
            }
        await WebSocket.send_json(ws, payload)
       
               
    async def color_plus_plus(self, ws: WebSocket) ->None:
        sess = self.sessions.get(ws)
        if not sess:
            return 
    
        # board_before = self.world.ensure_chunk(sess.state.chunk_id).clone()
        # players_before = self.chunk_players.get_players_in_chunk(sess.state.chunk_id)
        
        # self.world.user_logs.append(
        #     sess.state.user_id,
        #     sess.state.chunk_id,
        #     sess.state.pos.row,
        #     sess.state.pos.col,
        #     ActionToken.COLOR,
        # )
        
        
        self.user_logger.append(
            sess.state.user_id,
            sess.state.chunk_id,
            sess.state.pos.row,
            sess.state.pos.col,
            ActionToken.COLOR
        )
        self.color_service.color_plus_plus(sess.state)
        await self.scrolls.broadcast_chunk(sess.state.chunk_id)