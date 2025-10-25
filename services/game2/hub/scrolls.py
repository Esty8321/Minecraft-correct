#V
from __future__ import annotations
import logging
from typing import Set
from fastapi import WebSocket
from .types import MatrixPayload
from .ws_utils import  WebSocketUtils
from .sessions import SessionStore
from .world import WorldService
from ..core.settings import W, H, BIT_HAS_LINK
from ..core.bits import get_bit, set_bit
from ..data.db_scrolls import  ScrollDB

from ..data.db_history import PlayerActionHistory
from .scroll_message import ScrollMessage

from services.game2.hub import sessions
from ..data.db_chunks import ChunkDB
logger = logging.getLogger(__name__)

class ScrollService:
    """Manages in-world scroll messages, including broadcasting updates to all watchers in a chunk."""
    def __init__(self, world: WorldService, sessions: SessionStore, scroll_db : ScrollDB, chunk_db: ChunkDB,player_action_history: PlayerActionHistory ) -> None:
        self.world = world
        self.sessions = sessions
        
        self.scroll_db = scroll_db
        self.chunk_db = chunk_db
        self.player_action_history = player_action_history

    
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
            ok = await WebSocketUtils.send_json(ws, payload)
            if not ok:
             dead.add(ws)
        for ws in dead:
            self.sessions.pop(ws)
            
        
    async def maybe_send_scroll_at(self, ws: WebSocket) -> None:
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
        msg = self.scroll_db.load_scroll(state.chunk_id, state.pos.row, state.pos.col)
        if msg:
            await WebSocketUtils.send_json(ws, {"type": "message", "data": msg})
            sess.last_msg_pos = current_pos
        else:
         sess.last_msg_pos = None

    async def write_scroll(self, ws: WebSocket, content: str) -> None:
        sess = self.sessions.get(ws)
        if not sess:
            return
        state = sess.state
        board = self.world.ensure_chunk(state.chunk_id)
        existing = self.scroll_db.load_scroll(state.chunk_id, state.pos.row, state.pos.col)
        if existing or get_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK):
            await WebSocketUtils.send_json(ws, {
                "type": "error",
                "code": "SPACE_OCCUPIED",
                "message": "This spot already has a message!",
                })
            return
        scroll = ScrollMessage(
            content=content,
            author=sess.state.user_id or "unknown",
            chunk_id=state.chunk_id,
            position=(state.pos.row, state.pos.col),
            )
        self.scroll_db.save_scroll(scroll)
        board[state.pos.row, state.pos.col] = set_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK, True)
        state.underlying_cell = set_bit(state.underlying_cell, BIT_HAS_LINK, True)
        self.chunk_db.save_chunk(state.chunk_id, board)
        await self.broadcast_chunk(state.chunk_id)
        notice = {"type": "announcement", "data": {"text": "A player hid a treasure"}}
        for target_ws in list(self.sessions.watchers(state.chunk_id)):
            await WebSocketUtils.send_json(target_ws, notice)
            
  