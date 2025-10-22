from __future__ import annotations
import logging
from typing import Set
from fastapi import WebSocket
from .types import MatrixPayload
from .helper import send_json
from .sessions import SessionStore
from .world import WorldService
from ..core.settings import W, H, BIT_HAS_LINK
from ..core.bits import get_bit, set_bit
from ..data.db_messages import load_message, save_message
from ..models.message import Message
from services.game2.hub import sessions
from ..data.db_chunks import save_chunk


logger = logging.getLogger(__name__)

class MessagingService:
    def __init__(self, world: WorldService, sessions: SessionStore) -> None:
        self.world = world
        self.sessions = sessions
    
    #to see if I can insert here the broadcast to the user himself by  sess.by_user
    async def broadcast_chunk(self, chunk_id: str) -> None:
        board = self.world.ensure_chunk(chunk_id)
        payload: MatrixPayload = {
            "type": "matrix",
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": chunk_id,
            "total_players": self.sessions.player_count(),
        }   
        dead: Set[WebSocket] = set()
        for ws in list(self.sessions.watchers(chunk_id)):
            ok = await send_json(ws, payload)
            if not ok:
             dead.add(ws)
        for ws in dead:
            self.sessions.pop(ws)
            
        
    async def maybe_send_message_at(self, ws: WebSocket) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        board = self.world.ensure_chunk(state.chunk_id)
        cell_under = state.underlying_cell or board[state.pos.row, state.pos.col]
        current_pos = (state.chunk_id, state.pos.row, state.pos.col)

        if get_bit(cell_under, BIT_HAS_LINK):
            if sess.last_msg_pos == current_pos:
                return
        msg = load_message(state.chunk_id, state.pos.row, state.pos.col)
        if msg:
            await send_json(ws, {"type": "message", "data": msg})
            sess.last_msg_pos = current_pos
        else:
         sess.last_msg_pos = None

    async def write_message(self, ws: WebSocket, content: str) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        board = self.world.ensure_chunk(state.chunk_id)
        existing = load_message(state.chunk_id, state.pos.row, state.pos.col)
        if existing or get_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK):
            await send_json(ws, {
                "type": "error",
                "code": "SPACE_OCCUPIED",
                "message": "This spot already has a message!",
                })
            return
        message = Message(
            content=content,
            author=sess.user_id or "unknown",
            chunk_id=state.chunk_id,
            position=(state.pos.row, state.pos.col),
            )
        save_message(message)
        board[state.pos.row, state.pos.col] = set_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK, True)
        state.underlying_cell = set_bit(state.underlying_cell, BIT_HAS_LINK, True)
        save_chunk(state.chunk_id, board)
        await self.broadcast_chunk(state.chunk_id)
        notice = {"type": "announcement", "data": {"text": "A player hid a treasure"}}
        for target_ws in list(self.sessions.watchers(state.chunk_id)):
            await send_json(target_ws, notice)
            
            
    async def record_player_action(self, user_id: str, chunk_id: str, dr: int, dc: int, board):
        """Save the player's move to the action history (non-blocking)."""
        from .types import MOVE_TOKENS
        from ..data.db_history import append_player_action

        token = MOVE_TOKENS.get((dr, dc))
        if not token:
            return
        try:
            append_player_action(user_id, chunk_id, token, board)
        except Exception:
            pass

    async def update_watchers_after_chunk_change(self, user_id: str, old_chunk_id: str, new_chunk_id: str):
        """Detach this player's sockets from old chunk and attach to new one."""
        if not old_chunk_id or old_chunk_id == new_chunk_id:
            return
        for ws in self.sessions.sockets_for_user(user_id):
            self.sessions.detach_watcher(old_chunk_id, ws)
            self.sessions.attach_watcher(new_chunk_id, ws)

    async def broadcast_player_move(self, user_id: str, ws: WebSocket, chunk_id: str):
        """Send matrix update to all relevant sockets (player & others)."""
        # broadcast chunk to everyone watching
        await self.broadcast_chunk(chunk_id)
        # re-broadcast for all same-user sockets to keep them in sync
        for other_ws in self.sessions.sockets_for_user(user_id):
            if other_ws != ws:
                await self.broadcast_chunk(chunk_id)
        await self.maybe_send_message_at(ws)
