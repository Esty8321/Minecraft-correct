import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

from datetime import datetime


#pass it to the setting file and at the main file do the mkdir function
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHAT_DB_PATH = DATA_DIR / "chat.db"

class ChatDB:
    """
    SQLite storage for chat messages.
    Indexed by (sender_id, receiver_id).
    """

    def __init__(self, db_path: Path = CHAT_DB_PATH):
        self.db_path = db_path
        self._init_db()


    def _connect(self):
        """Create and return a SQLite connection."""
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Create the messages table and index if needed."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                content TEXT NOT NULL,
                reaction TEXT DEFAULT 'none'
            )
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_sender_receiver
            ON messages (sender_id, receiver_id)
            """)
            conn.commit()


    def add_message(self, sender_id: str, receiver_id: str, content: str,
                    timestamp: Optional[str] = None, reaction: str = "none") -> Dict:
        """
        Add a message to the chat DB.
        Returns a dict with message info (id, from, to, content, timestamp, reaction).
        """
        ts = timestamp or datetime.utcnow().isoformat() + "Z"
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO messages (timestamp, sender_id, receiver_id, content, reaction)
                VALUES (?, ?, ?, ?, ?)
            """, (ts, sender_id, receiver_id, content, reaction))
            conn.commit()
            msg_id = cur.lastrowid
            return {
            "id": msg_id,
            "timestamp": ts,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content,
            "reaction": reaction
        }


    def get_messages_between(self, a: str, b: str) -> List[Dict]:
        """
        Return all messages between two players, ordered by time ascending.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM messages
                WHERE (sender_id=? AND receiver_id=?)
                   OR (sender_id=? AND receiver_id=?)
                ORDER BY timestamp ASC
            """, (a, b, b, a))
            rows = cur.fetchall()
            return [dict(r) for r in rows]


    def get_message_by_id(self, msg_id: int) -> Optional[Dict]:
        """
        Retrieve one message by ID.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM messages WHERE id=?", (msg_id,))
            row = cur.fetchone()
            return dict(row) if row else None


    def update_reaction(self, msg_id: int, reaction: str) -> bool:
        """
        Update a message reaction (like/dislike/none).
        Returns True if update succeeded.
        """
        if reaction not in ("like", "dislike", "none"):
            raise ValueError("Invalid reaction value")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE messages SET reaction=? WHERE id=?", (reaction, msg_id))
            conn.commit()
            return cur.rowcount > 0