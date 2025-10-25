import sqlite3, time
from typing import Optional, List
import numpy as np
import torch
from ..core.settings import DB_PATH, W, H, DTYPE

class ChunkDB:
    """Handles persistence of world chunks (boards) in SQLite.
    Each chunk is stored as a flat uint8 tensor blob."""

    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          data BLOB NOT NULL,
          last_used INTEGER
        )
        """)

        self._maybe_migrate_old_schema()
    def _maybe_migrate_old_schema(self) -> None:
           try:
               cols = [r[1] for r in self.conn.execute("PRAGMA table_info(chunks)")]
           except sqlite3.OperationalError:
               cols = []
           if "w" in cols or "h" in cols:
               self.conn.execute("""
               CREATE TABLE IF NOT EXISTS chunks_new (
                 id TEXT PRIMARY KEY,
                 data BLOB NOT NULL,
                 last_used INTEGER
               )
               """)
               self.conn.execute("""
               INSERT INTO chunks_new (id, data, last_used)
               SELECT id, data, last_used FROM chunks
               """)
               self.conn.execute("DROP TABLE chunks")
               self.conn.execute("ALTER TABLE chunks_new RENAME TO chunks")
    
           try:
               cols = [r[1] for r in self.conn.execute("PRAGMA table_info(chunks)")]
           except Exception as e:
               print(f"[db_chunks] debug failed: {e}")
   
    def save_chunk(self, cid: str, data_t: torch.Tensor) -> None:
        assert data_t.dtype == torch.uint8 and data_t.shape == (H, W)
        arr = data_t.numpy().astype(np.uint8, copy=False)
        blob = arr.tobytes(order="C")
        now  = int(time.time())
        self.conn.execute("""
            INSERT INTO chunks (id, data, last_used)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              data=excluded.data,
              last_used=excluded.last_used
        """, (cid, blob, now))

    def load_chunk(self, cid: str) -> Optional[torch.Tensor]:
        row = self.conn.execute("SELECT data FROM chunks WHERE id=?", (cid,)).fetchone()
        if not row:
            return None
        (blob,) = row
        arr = np.frombuffer(blob, dtype=np.uint8, count=W*H).reshape(H, W)
        self.conn.execute("UPDATE chunks SET last_used=? WHERE id=?", (int(time.time()), cid))
        return torch.tensor(arr, dtype=DTYPE)

    def list_chunk_ids(self) -> List[str]:
        return [r[0] for r in self.conn.execute("SELECT id FROM chunks").fetchall()]

