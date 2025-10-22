import math
import sqlite3, time
from typing import Optional, Tuple
from ..core.settings import PLAYERS_DB_PATH
from ..data import db_chunks



class PlayerDB:
    """Track per-player last known chunk + position in players.db."""

    def __init__(self, db_path=PLAYERS_DB_PATH):
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

    def get_position(self, player_id: str) -> Optional[Tuple[str, int, int]]:
        r = self.conn.execute("SELECT chunk_id, row, col FROM players WHERE id=?", (player_id,)).fetchone()
        return r if r else None

    def upsert_position(self, player_id: str, chunk_id: str, row: int, col: int) -> None:
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

_db = PlayerDB()
def get_player_position(pid: str) -> Optional[Tuple[str, int, int]]: return _db.get_position(pid)
def save_player_position(pid: str, cid: str, row: int, col: int) -> None: _db.upsert_position(pid, cid, row, col)



def find_nearest_player_in_chunk(current_id: str)->Optional[str]:
    me = _db.get_position(current_id)
    if not me:
        return None
    chunk_id, my_row, my_col = me
    cur = _db.conn.cursor()
    cur.execute(
        "SELECT id, row, col FROM players WHERE chunk_id=? AND id!=?",
        (chunk_id, current_id)
    )
    others = cur.fetchall()
    if not others:
        return None
    board = db_chunks.load_chunk(chunk_id)
    nearest = None
    nearest_dist = float("inf")
    for pid, r, c in others:
        dist = math.hypot(r - my_row, c - my_col)
        if dist < nearest_dist:
            nearest = pid
            nearest_dist = dist
    return nearest
    

    
    
        

