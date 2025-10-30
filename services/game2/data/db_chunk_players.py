import sqlite3
import os

CHUNK_PLAYERS_DB_PATH = os.path.join("data", "chunk_players.db")

class ChunkPlayersDB:
    """Manages the SQLite DB that tracks which players are in which chunk (with position)."""

    def __init__(self, db_path: str = CHUNK_PLAYERS_DB_PATH):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS chunk_players (
            chunk_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            row INTEGER NOT NULL,
            col INTEGER NOT NULL,
            PRIMARY KEY (chunk_id, user_id)
        )
        """)

        print(f"[ChunkPlayersDB] Table 'chunk_players' ensured in {db_path}")

 
    def add_player(self, chunk_id: str, user_id: str, row: int, col: int):
        """Add or update player position in the DB."""
        self.conn.execute("""
        INSERT INTO chunk_players (chunk_id, user_id, row, col)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chunk_id, user_id)
        DO UPDATE SET row=excluded.row, col=excluded.col
        """, (chunk_id, user_id, row, col))

    def remove_player(self, chunk_id: str, user_id: str):
        """Remove player from chunk."""
        self.conn.execute(
            "DELETE FROM chunk_players WHERE chunk_id=? AND user_id=?",
            (chunk_id, user_id),
        )

    def list_players(self, chunk_id: str):
        """Return all players (user_id, row, col) in the given chunk."""
        cur = self.conn.execute(
            "SELECT user_id, row, col FROM chunk_players WHERE chunk_id=?",
            (chunk_id,),
        )
        return [{"id": r[0], "row": r[1], "col": r[2]} for r in cur.fetchall()]

    def clear_chunk(self, chunk_id: str):
        self.conn.execute("DELETE FROM chunk_players WHERE chunk_id=?", (chunk_id,))

    def close(self):
        self.conn.close()
