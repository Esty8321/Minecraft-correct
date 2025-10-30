from __future__ import annotations
from typing import List, Optional
from datetime import datetime

from ..data.db_chat import ChatDB
class MessageService:
    """
    Handles all message storage and retrieval logic.
    Uses ChatDB internally (SQLite) for persistence.
    """

    def __init__(self, db: ChatDB):
        self.db = db


    def append_message(
        self,
        sender_id: str,
        receiver_id: str,
        text: str,
        timestamp: Optional[str] = None,
        quoted_id: Optional[str] = None,
    ) -> dict:
        timestamp = timestamp or datetime.utcnow().isoformat() + "Z"
        self.db.add_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=text,
            timestamp=timestamp,
            reaction="none"
        )

        msg_id = f"{sender_id}_{receiver_id}_{timestamp}"

        return {
            "id": msg_id,
            "from": sender_id,
            "to": receiver_id,
            "message": text,
            "timestamp": timestamp,
            "reaction": "none",
        }

   
   
    def history_between(self, a: str, b: str, viewer: Optional[str] = None) -> List[dict]:
        msgs = self.db.get_messages_between(a, b)
        return [self._minimal_view(m, viewer) for m in msgs]



    def get_message_by_id(self, msg_id: str) -> Optional[dict]:
        return self.db.get_message_by_id(msg_id)



    def update_reaction(self, msg_id: int, reaction: str) -> None:
        self.db.update_reaction(msg_id, reaction)


    def _minimal_view(self, m: dict, viewer: Optional[str] = None) -> dict:
        """Return a compact representation of a message, handling all key formats."""
        sender = m.get("sender_id") or m.get("from")
        receiver = m.get("receiver_id") or m.get("to")
        content = m.get("content") or m.get("message", "")
        timestamp = m.get("timestamp")
    
        view = {
            "id": m["id"],
            "from": sender,
            "to": receiver,
            "message": content,
            "timestamp": timestamp,
            "reaction": m.get("reaction", "none"),
        }    
        if viewer:
            view["my_reaction"] = m.get("reaction") if m.get("sender_id") != viewer else None 
        return view
    