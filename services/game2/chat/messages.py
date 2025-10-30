# from __future__ import annotations
# from typing import List, Optional, Dict
# from datetime import datetime
# from ..data.db_chat import ChatDB


# # -----------------------------
# # Initialize global DB instance
# # -----------------------------
# db = ChatDB()


# # -----------------------------
# # 💬 Helpers
# # -----------------------------
# def minimal_view(m: dict, viewer: Optional[str] = None) -> dict:
#     v = {
#         "id": m["id"],
#         "from": m["sender_id"] if "sender_id" in m else m.get("from"),
#         "to": m["receiver_id"] if "receiver_id" in m else m.get("to"),
#         "message": m.get("content", m.get("message", "")),
#         "timestamp": m["timestamp"],
#         "deleted": False,
#         "read_by": [],
#     }
#     v["reaction"] = m.get("reaction", "none")
#     if viewer:
#         v["my_reaction"] = m.get("reaction")
#     return v


# # -----------------------------
# # ✉️ Append new message
# # -----------------------------
# def append_message(fr: str, to: str, text: str, ts: Optional[str] = None, quoted_id: Optional[str] = None) -> dict:
#     print("Inserting new message into SQLite...")
#     msg = db.insert_message(fr, to, text)
#     return msg


# # -----------------------------
# # 🔍 Get by message id
# # -----------------------------
# def get_message_by_id(mid: str) -> Optional[dict]:
#     try:
#         mid_int = int(mid)
#     except ValueError:
#         return None
#     return db.get_message_by_id(mid_int)


# # -----------------------------
# # 🕓 History between two players
# # -----------------------------
# def history_between(a: str, b: str, viewer: Optional[str] = None) -> List[dict]:
#     msgs = db.get_conversation(a, b)
#     out = [minimal_view(m, viewer) for m in msgs]
#     return out[-128:]  # cap to 128 last messages like before


# # -----------------------------
# # 🟢 Unread / Read helpers (placeholders)
# # -----------------------------
# def unread_count_for(me: str, from_id: str) -> int:
#     # SQLite version doesn’t track read/unread state yet
#     return 0

# def mark_read_pair(me: str, with_id: str) -> int:
#     # Stub for compatibility
#     return 0

# def unread_summary_for(me: str) -> Dict[str, int]:
#     return {}

# # -----------------------------
# # ❌ Soft delete message
# # -----------------------------
# def soft_delete_message_by_id(message_id: str, requester_id: str) -> Optional[dict]:
#     m = get_message_by_id(message_id)
#     if not m:
#         return None
#     if m["sender_id"] != requester_id:
#         return None
#     # We could delete or mark as deleted in DB (not required in schema)
#     return m


from __future__ import annotations
from typing import List, Optional, Dict
from datetime import datetime

from ..data.db_chat import ChatDB   # the SQLite manager class


class MessageService:
    """
    Handles all message storage and retrieval logic.
    Uses ChatDB internally (SQLite) for persistence.
    """

    def __init__(self, db: ChatDB):
        self.db = db

    # -----------------------------------------
    # Create / append new message
    # -----------------------------------------
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

    # -----------------------------------------
    # Retrieve history between two users
    # -----------------------------------------
    def history_between(self, a: str, b: str, viewer: Optional[str] = None) -> List[dict]:
        msgs = self.db.get_messages_between(a, b)
        return [self._minimal_view(m, viewer) for m in msgs]

    # -----------------------------------------
    # Get one message by DB ID
    # -----------------------------------------
    def get_message_by_id(self, msg_id: str) -> Optional[dict]:
        return self.db.get_message_by_id(msg_id)

    # -----------------------------------------
    # Update reaction
    # -----------------------------------------
    def update_reaction(self, msg_id: int, reaction: str) -> None:
        self.db.update_reaction(msg_id, reaction)

    # -----------------------------------------
    # Soft delete message (sender only)
    # -----------------------------------------
    def soft_delete_message(self, msg_id: int, requester_id: str) -> Optional[dict]:
        self.db.soft_delete_message(msg_id, requester_id)
        return self.db.get_message_by_id(msg_id)

    # -----------------------------------------
    # Helper for minimal frontend-friendly view
    # -----------------------------------------
    # def _minimal_view(self, m: dict, viewer: Optional[str] = None) -> dict:
    #     v = {
    #         "id": m["id"],
    #         "from": m["sender_id"],
    #         "to": m["receiver_id"],
    #         "message": m.get("content", ""),
    #         "timestamp": m["timestamp"],
    #         "reaction": m.get("reaction", "none"),
    #     }
    #     return v
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
    
        # Keep my_reaction if this viewer is the one who reacted
        if viewer:
            view["my_reaction"] = m.get("reaction") if m.get("sender_id") != viewer else None
    
        return view
    