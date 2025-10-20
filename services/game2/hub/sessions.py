from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
from fastapi import WebSocket


from .types import PlayerState

@dataclass
class PlayerSession:
   user_id: str
   state: PlayerState
   last_msg_pos: Optional[Tuple[str, int, int]] = None # (chunk_id, r, c)

class SessionStore:
    """Keeps track of live sockets, their sessions, and chunk watchers."""


    def __init__(self) -> None:
        self.sockets: Set[WebSocket] = set()
        self.by_ws: Dict[WebSocket, PlayerSession] = {}
        self.watchers_by_chunk: Dict[str, Set[WebSocket]] = {}


    # --- sockets / sessions ---
    def add(self, ws: WebSocket, session: PlayerSession) -> None:
        self.sockets.add(ws)
        self.by_ws[ws] = session
        self.watchers_by_chunk.setdefault(session.state.chunk_id, set()).add(ws)


    def get(self, ws: WebSocket) -> Optional[PlayerSession]:
        return self.by_ws.get(ws)


    def pop(self, ws: WebSocket) -> Optional[PlayerSession]:
        sess = self.by_ws.pop(ws, None)
        self.sockets.discard(ws)
        if sess:
          self.watchers_by_chunk.get(sess.state.chunk_id, set()).discard(ws)
        return sess


    # --- chunk watchers ---
    def attach_watcher(self, chunk_id: str, ws: WebSocket) -> None:
        self.watchers_by_chunk.setdefault(chunk_id, set()).add(ws)


    def detach_watcher(self, chunk_id: str, ws: WebSocket) -> None:
        self.watchers_by_chunk.get(chunk_id, set()).discard(ws)


    def watchers(self, chunk_id: str) -> Set[WebSocket]:
        return self.watchers_by_chunk.get(chunk_id, set())


    # --- stats ---
    def player_count(self) -> int:
        return len(self.sockets)