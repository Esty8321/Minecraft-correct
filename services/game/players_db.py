import sqlite3
from pathlib import Path
from typing import Optional, Tuple
import time

# Base path for data folder (same logic as db.py)
BASE_ROOT_DIR = Path(__file__).resolve().parents[2]
PLAYER_DB_PATH = BASE_ROOT_DIR / "data" / "players.db"

class PlayerDB:
    def __init__(self, db_path: Path = PLAYER_DB_PATH):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL,
            row INTEGER NOT NULL,
            col INTEGER NOT NULL,
            last_seen INTEGER
        )
        """)

    def get_player_position(self, player_id: str) -> Optional[Tuple[str, int, int]]:
        cur = self.conn.execute(
            "SELECT chunk_id, row, col FROM players WHERE id=?", (player_id,)
        )
        row = cur.fetchone()
        if row:
            return row  # (chunk_id, row, col)
        return None

    def upsert_player_position(self, player_id: str, chunk_id: str, row: int, col: int) -> None:
        now = int(time.time())
        self.conn.execute("""
        INSERT INTO players (id, chunk_id, row, col, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          chunk_id=excluded.chunk_id,
          row=excluded.row,
          col=excluded.col,
          last_seen=excluded.last_seen
        """, (player_id, chunk_id, row, col, now))

# Global singleton instance
_player_db = PlayerDB()

def get_player_position(player_id: str) -> Optional[Tuple[str, int, int]]:
    return _player_db.get_player_position(player_id)

def save_player_position(player_id: str, chunk_id: str, row: int, col: int) -> None:
    _player_db.upsert_player_position(player_id, chunk_id, row, col)
