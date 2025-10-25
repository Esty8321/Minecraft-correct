import math
import sqlite3, time
from typing import Optional, Tuple, List
from ..core.settings import PLAYERS_DB_PATH
from ..data import db_chunks



class PlayerDB:
    """Manages player positions and last-known locations in the world.
    Stores player state (chunk, row, col) in players.db."""
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
        row = self.conn.execute("SELECT chunk_id, row, col FROM players WHERE id=?", (player_id,)).fetchone()
        return row if row else None

    def save_position(self, player_id: str, chunk_id: str, row: int, col: int) -> None:
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

    def list_players_in_chunk(self, chunk_id: str, exclude_id: Optional[str] = None)->List[Tuple[str, int, int]]:
        "Return all players in a given chunk"
        cur = self.conn.cursor()   
        if exclude_id:
            cur.execute(
                "SELECT id, row, col FROM players WHERE chunk_id=? AND id!=?",
                (chunk_id, exclude_id),
            )  
        else:
             cur.execute("SELECT id, row, col FROM players WHERE chunk_id=?", (chunk_id,))
        return cur.fetchall()
   
    def close(self)->None:
        """Close the database connection."""
        self.conn.close()





    
    
        

