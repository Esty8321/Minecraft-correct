import sqlite3, time
from typing import Optional, List
import numpy as np
import torch
from ..core.settings import DB_PATH, W, H, DTYPE

class ChunkDB:
    """Persist chunks (boards) as flat uint8 blobs in SQLite (world.db)."""

    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          w INTEGER NOT NULL,
          h INTEGER NOT NULL,
          data BLOB NOT NULL,
          last_used INTEGER
        )
        """)

    def save_chunk(self, cid: str, data_t: torch.Tensor) -> None:
        assert data_t.dtype == torch.uint8 and data_t.shape == (H, W)
        arr = data_t.numpy().astype(np.uint8, copy=False)
        blob = arr.tobytes(order="C")
        now  = int(time.time())
        self.conn.execute("""
            INSERT INTO chunks (id, w, h, data, last_used)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              w=excluded.w,
              h=excluded.h,
              data=excluded.data,
              last_used=excluded.last_used
        """, (cid, W, H, blob, now))

    def load_chunk(self, cid: str) -> Optional[torch.Tensor]:
        row = self.conn.execute("SELECT data, w, h FROM chunks WHERE id=?", (cid,)).fetchone()
        if not row:
            return None
        blob, w, h = row
        arr = np.frombuffer(blob, dtype=np.uint8, count=w*h).reshape(h, w)
        self.conn.execute("UPDATE chunks SET last_used=? WHERE id=?", (int(time.time()), cid))
        return torch.tensor(arr, dtype=DTYPE)

    def list_chunk_ids(self) -> List[str]:
        return [r[0] for r in self.conn.execute("SELECT id FROM chunks").fetchall()]

_db = ChunkDB()
def save_chunk(cid: str, data: torch.Tensor) -> None: _db.save_chunk(cid, data)
def load_chunk(cid: str) -> Optional[torch.Tensor]:   return _db.load_chunk(cid)
