from __future__ import annotations
import json
import logging
from typing import Optional
import torch
from fastapi import WebSocket

from services.game2.core.settings import W, H
from services.game2.data.db_messages import save_message, load_message
from services.game2.data.db_history import append_player_action, ActionToken
from services.game2.data.db_chunks import save_chunk
from services.game2.hub.types import PlayerState, MatrixPayload
from services.game2.hub.sessions import SessionStore
from services.game2.hub.message import Message
from services.game2.core.bits import set_bit, get_bit
from services.game2.core.settings import BIT_HAS_LINK, DTYPE
from services.game2.hub.world import WorldService


logger = logging.getLogger(__name__)

class ScrollService:
    def __init__(self, sessions: SessionStore, world: WorldService):
        self.sessions = sessions
        self.world = world

    async def broadcast_chunk(self, chunk_id: str, board: Optional[torch.Tensor] = None) -> None:
        if board is None:
            return
        payload: MatrixPayload = {
            "type": "matrix",
            "w": W, "h": H,
            "data": board.detach().cpu().numpy().astype(int).ravel().tolist(),
            "chunk_id": chunk_id,
            "total_players": self.sessions.count_players_in_chunk(chunk_id),
        }
        await self.sessions.fanout_chunk_text(chunk_id, json.dumps(payload, ensure_ascii=False))

    async def announce(self, chunk_id: str, text_msg: str) -> None:
        await self.sessions.fanout_chunk_text(
            chunk_id,
            json.dumps({"type": "announcement", "data": {"text": text_msg}}, ensure_ascii=False)
        )

    
  
    async def write_treasure_message(self, state: PlayerState, content: str) -> bool:
        r, c = state.pos.row, state.pos.col
        msg = Message(
            content=content,
            author=state.user_id,
            chunk_id=state.chunk_id,
            position=(r, c),
        )
        save_message(msg)
        board = self.world.ensure_chunk(state.chunk_id)
        try:
            vis_val = int(board[r, c].item())
            if not get_bit(vis_val, BIT_HAS_LINK):
                vis_val = int(set_bit(vis_val, BIT_HAS_LINK, True))
                board[r, c] = torch.tensor(vis_val, dtype=DTYPE)
        except Exception as e:
                logger.warning("Failed to update BIT_HAS_LINK at (%s, %s): %s", r, c, e)

        save_chunk(state.chunk_id, board)
        try:
            append_player_action(state.user_id, state.chunk_id, ActionToken.DM, board)
        except Exception as e:
           logger.warning("Failed to append DM action for user %s: %s", state.user_id, e)
        await self.announce(state.chunk_id, "A player hid a treasure")
        await self.broadcast_chunk(state.chunk_id, board)
        return True
    


    async def maybe_send_message_at(self, ws: WebSocket, state: PlayerState) -> None:
        r, c = state.pos.row, state.pos.col
        key = (state.chunk_id, r, c)
        if state.last_msg_pos == key:
            return
        doc = load_message(state.chunk_id, r, c)
        if not doc:
            return
        state.last_msg_pos = key
        try:
            await ws.send_text(json.dumps({"type": "message", "data": doc}, ensure_ascii=False))
        except Exception:
            logger.debug("failed to send message payload to player=%s", state.user_id)
