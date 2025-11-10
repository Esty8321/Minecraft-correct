from __future__ import annotations
import logging
from typing import Set, List, Dict, Tuple  
from fastapi import WebSocket
from .types import MatrixPayload, ActionToken
from .ws_utils import WebSocketUtils
from .sessions import SessionStore
from .world import WorldService
from ..core.settings import W, H, BIT_HAS_LINK_IDX, DTYPE
from ..core.bits import get_bit
from ..data.db_scrolls import ScrollDB
from ..data.db_players import PlayerDB
from ..data.db_history import PlayerActionHistory
from .scroll_message import ScrollMessage
import torch
from ..data.db_chunks import ChunkDB
from ..data.db_scores import ScoresDB
from datetime import datetime
logger = logging.getLogger(__name__)

class ScrollService:
    """Manages in-world scroll messages, including broadcasting updates to all watchers in a chunk."""
    def __init__(
        self,
        world: WorldService,
        sessions: SessionStore,
        scroll_db: ScrollDB,
        chunk_db: ChunkDB,
        player_action_history: PlayerActionHistory,
        player_db: PlayerDB,
        scores_db: ScoresDB, 
    ) -> None:
        self.world = world
        self.sessions = sessions
        self.scroll_db = scroll_db
        self.chunk_db = chunk_db
        self.player_action_history = player_action_history
        self.player_db = player_db
        self.scores_db = scores_db

        #        map: user_id -> (scroll_id, chunk_id, row, col)
        self._pending_cleanup: Dict[str, Tuple[str, str, int, int]] = {}

    def _players_in_chunk_payload(self, chunk_id: str) -> List[dict]:
        rows = self.player_db.list_players_in_chunk(chunk_id)
        return [{"id": pid, "row": r, "col": c} for (pid, r, c) in rows]
       
    async def broadcast_chunk(self, chunk_id: str) -> None:
        board = self.world.ensure_chunk(chunk_id)
        payload: MatrixPayload = {
            "type": "matrix",
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": chunk_id,
            "total_players": self.sessions.player_count(),
            "players": self._players_in_chunk_payload(chunk_id),
        }
        dead: Set[WebSocket] = set()
        for ws in list(self.sessions.watchers(chunk_id)):
            ok = await WebSocketUtils.send_json(ws, payload)
            if not ok:
                dead.add(ws) 
        for ws in dead:
            self.sessions.pop(ws)

    async def maybe_send_scroll_at(self, ws: WebSocket) -> None:
        try:
            sess = self.sessions.get(ws)
            if not sess:
                return
            state = sess.state
            board = self.world.ensure_chunk(state.chunk_id)

            cell = board[state.pos.row, state.pos.col]
            current_pos = (state.chunk_id, state.pos.row, state.pos.col)

            if get_bit(cell, BIT_HAS_LINK_IDX):
                if getattr(sess, "last_msg_pos", None) == current_pos:
                    return
                msg = await self.scroll_db.load_scroll(state.chunk_id, state.pos.row, state.pos.col)
                if msg:
                    content = msg["content"] if isinstance(msg, dict) else getattr(msg, "content", str(msg))
                    await WebSocketUtils.send_json(ws, {
                        "type": "announcement",
                        "data": {"text": content}
                    })
                    sess.last_msg_pos = current_pos
                    return
            sess.last_msg_pos = None
        except Exception as e:
            print("error---", e)

    async def write_scroll(self, ws: WebSocket, content: str) -> None:
        try:
            sess = self.sessions.get(ws)
            if not sess:
                return
            state = sess.state
            board = self.world.ensure_chunk(state.chunk_id)

            existing = await self.scroll_db.load_scroll(state.chunk_id, state.pos.row, state.pos.col)
            if existing or get_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK_IDX):
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

            await self.scroll_db.save_scroll(scroll)
            v = int(board[state.pos.row, state.pos.col].item())
            v = v | (1 << 6)
            board[state.pos.row, state.pos.col] = torch.tensor(v, dtype=DTYPE)

            self.chunk_db.save_chunk(state.chunk_id, board)

            try:
                self.player_action_history.append_player_action(
                    sess.state.user_id,
                    state.chunk_id,
                    ActionToken.DM,
                    board,
                )
            except Exception as e:
                logger.warning("Failed to append history: %s", e)

            await self.broadcast_chunk(state.chunk_id)

            notice = {"type": "announcement", "data": {"text": "A player hid a treasure"}}
            for target_ws in list(self.sessions.watchers(state.chunk_id)):
                await WebSocketUtils.send_json(target_ws, notice)
        except Exception as e:
            print("error in write the message: ", e)

    async def on_enter_cell(self, user_id: str, chunk_id: str, row: int, col: int) -> None:
        try:
            print(f"[ENTER_CELL] user={user_id} chunk={chunk_id} r={row} c={col}")
            msg = await self.scroll_db.load_scroll(chunk_id, row, col)
            if not msg:
                print("[ENTER_CELL] no scroll found here")
                return

            author_id = (msg.get("author") or msg.get("author_user_id") or "")
            found_by  = msg.get("found_by_user_id")
            print(f"[ENTER_CELL] author={author_id}, found_by={found_by}")

            if author_id == user_id:
                print("[ENTER_CELL] skipping: player is author")
                return

            updated = await self.scroll_db.mark_found_if_null(msg_id=msg["id"], found_by_user_id=user_id)
            print(f"[ENTER_CELL] mark_found_if_null -> {updated}")

            if updated:
                self.scores_db.add_score(user_id, 10)
                self._pending_cleanup[user_id] = (msg["id"], chunk_id, row, col)
                try:
                    get_ws_by_user = getattr(self.sessions, "get_ws_by_user", None)
                    if callable(get_ws_by_user):
                        user_ws = get_ws_by_user(user_id)
                        if user_ws:
                            await WebSocketUtils.send_json(
                                user_ws,
                                {"type": "score_update", "delta": 10, "reason": "scroll_found",
                                 "row": row, "col": col, "chunk_id": chunk_id}
                            )
                except Exception as e:
                    logger.debug("score_update notify failed: %s", e)

        except Exception as e:
            logger.warning("on_enter_cell failed: %s", e)


    async def on_leave_cell(self, user_id: str, chunk_id: str, row: int, col: int) -> None:
        try:
            info = self._pending_cleanup.get(user_id)
            if not info:
                return
            scroll_id, found_chunk_id, found_row, found_col = info
            await self.scroll_db.delete_scroll_by_id(scroll_id)
            board = self.world.ensure_chunk(found_chunk_id)
            v = int(board[found_row, found_col].item())
            if get_bit(v, BIT_HAS_LINK_IDX):
                v = v & ~(1 << BIT_HAS_LINK_IDX)
                board[found_row, found_col] = torch.tensor(v, dtype=DTYPE)
                self.chunk_db.save_chunk(found_chunk_id, board)
            await self.broadcast_chunk(found_chunk_id)
            self._pending_cleanup.pop(user_id, None)

        except Exception as e:
            logger.warning("on_leave_cell failed: %s", e)
