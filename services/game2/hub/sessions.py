from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
from fastapi import WebSocket


from .types import PlayerState

@dataclass
class PlayerSession:
   state: PlayerState
   last_msg_pos: Optional[Tuple[str, int, int]] = None

class SessionStore:
    """Keeps track of live sockets, their sessions, and chunk watchers."""


    def __init__(self) -> None:
        self.sockets: Set[WebSocket] = set()
        self.by_ws: Dict[WebSocket, PlayerSession] = {}
        self.watchers_by_chunk: Dict[str, Set[WebSocket]] = {}
        self.by_user: Dict[str, Set[WebSocket]] = {}

    def add(self, ws: WebSocket, session: PlayerSession) -> None:
        self.sockets.add(ws)
        self.by_ws[ws] = session
        self.watchers_by_chunk.setdefault(session.state.chunk_id, set()).add(ws)
        self.by_user.setdefault(session.state.user_id, set()).add(ws)

    def get(self, ws: WebSocket) -> Optional[PlayerSession]:
        return self.by_ws.get(ws)

    def pop(self, ws: WebSocket) -> Optional[PlayerSession]:
        sess = self.by_ws.pop(ws, None)
        self.sockets.discard(ws)
        if sess:
            self.watchers_by_chunk.get(sess.state.chunk_id, set()).discard(ws)
            user_ws_set = self.by_user.get(sess.state.user_id)
            if user_ws_set:
                user_ws_set.discard(ws)
                if not user_ws_set:
                    self.by_user.pop(sess.state.user_id, None)
        return sess


    def attach_watcher(self, chunk_id: str, ws: WebSocket) -> None:
        self.watchers_by_chunk.setdefault(chunk_id, set()).add(ws)


    def detach_watcher(self, chunk_id: str, ws: WebSocket) -> None:
        self.watchers_by_chunk.get(chunk_id, set()).discard(ws)


    def watchers(self, chunk_id: str) -> Set[WebSocket]:
        return self.watchers_by_chunk.get(chunk_id, set())


    def player_count(self) -> int:
        return len(self.by_user)
    
    def find_by_user_id(self, user_id: str):
         for ws, sess in self.by_ws.items():
             if sess.state.user_id == user_id:
                 return ws, sess
         return None

    def sockets_for_user(self, user_id: str) -> Set[WebSocket]:##check if I realy need it
        return self.by_user.get(user_id, set())
