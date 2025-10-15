import sqlite3, time
from pathlib import Path
from typing import Optional, List
import numpy as np
import torch
from .settings import DB_PATH, W, H, DTYPE
import json
import os
from json import JSONDecodeError
from .models import Message
from .settings import DB_PATH, W, H, DTYPE

BASE_ROOT_DIR = Path(__file__).resolve().parents[2] 
MESSAGES_JSON_PATH = BASE_ROOT_DIR / "data" / "message.json"

class ChunkDB:
    def __init__(self, db_path: Path =DB_PATH):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")        
        except Exception as e:
            print('[DB] failed execute to the connection')
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          w INTEGER NOT NULL,
          h INTEGER NOT NULL,
          data BLOB NOT NULL,
          last_used INTEGER
        )
        """)

    def save_chunk(self, cid: str, data_t : torch.Tensor):
        assert data_t.dtype == torch.uint8
        arr = data_t.numpy().astype(np.uint8, copy = False)
        blob = arr.tobytes(order = "C")
        now = int(time.time())
        self.conn.execute(
             """
            INSERT INTO chunks (id, w, h, data, last_used)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              w=excluded.w,
              h=excluded.h,
              data=excluded.data,
              last_used=excluded.last_used
            """,
            (cid, W, H, blob, now),
        )

    def load_chunk(self, cid: str) -> Optional[torch.Tensor]:
        curr = self.conn.execute("SELECT data, w, h FROM chunks WHERE id=?", (cid,))
        row = curr.fetchone()
        if not row:
            return None
        blob, w, h = row
        arr = np.frombuffer(blob, dtype = np.uint8, count = w*h).reshape(h, w)
        self.conn.execute("UPDATE chunks SET last_used=? WHERE id=?", (int(time.time()), cid))
        return torch.tensor(arr, dtype=DTYPE)
    
    def list_chunk_ids(self) ->List[str]:
        curr = self.conn.execute("SELECT id FROM chunks")
        return [r[0] for r in curr.fetchall()]
    
    def clear_player_bits_all(self)-> None:
        curr = self.conn.execute("SELECT id, data, w, h FROM chunks")
        rows = curr.fetchall()
        now = int(time.time())
        for cid, blob, w, h in rows:
            arr = np.frombuffer(blob, dtype=np.uint8).copy()
            arr &= 0xFE
            new_blob = arr.tobytes(order = 'C')
            self.conn.execute(
                "UPDATE chunks SET data=?, last_used=? WHERE id=?",
                (new_blob, now, cid),
            )
            
#insert_text(board_id, r, c)

_db = ChunkDB()
def save_chunk(cid: str, data: torch.Tensor)-> None:
    _db.save_chunk(cid, data)

def load_chunk(cid: str)-> Optional[torch.Tensor]:
    return _db.load_chunk(cid)

def clear_player_bits_all()->None:
    _db.clear_player_bits_all()

def _safe_load_messages() -> dict:
    """טוען את קובץ ההודעות בבטחה (גם אם ריק/מקולקל)."""
    if not MESSAGES_JSON_PATH.exists():
        return {}
    try:
        with open(MESSAGES_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (JSONDecodeError, ValueError):
        return {}
def save_message(message: Message) -> None:
    """שומר הודעה חדשה בקובץ JSON"""
    try:
        print(f"[DEBUG] Saving message: {message.to_dict()}")
        MESSAGES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

        messages = _safe_load_messages()
        location_key = f"{message.chunk_id}_{message.position[0]}_{message.position[1]}"
        messages[location_key] = message.to_dict()

        # כתיבה אטומית
        tmp_path = MESSAGES_JSON_PATH.with_suffix(".tmp")
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, MESSAGES_JSON_PATH)

        print(f"[DEBUG] Message saved successfully to {MESSAGES_JSON_PATH}")
    except Exception as e:
        print(f"[ERROR] Failed to save message: {e}")
        raise
    
def get_message(chunk_id: str, row: int, col: int) -> dict | None:
    messages = _safe_load_messages()
    return messages.get(f"{chunk_id}_{row}_{col}")
  

def load_message(chunk_id: str, row: int, col: int) -> dict | None:
    """טוען הודעה מקובץ ה-JSON לפי מיקום"""
    try:
        messages = _safe_load_messages()
        return messages.get(f"{chunk_id}_{row}_{col}")
    except Exception as e:
        print(f"[game] Error loading message: {e}")
        return None
  