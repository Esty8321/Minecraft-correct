from collections import defaultdict
from typing import Dict, List
import threading
from ..data.db_chunk_players import ChunkPlayersDB
##?? to fix that he will not every time will save the data to the db

class ChunkPlayers:
    """
    Efficient in-memory + persistent mapping of chunk_id -> players (with row, col).
    Keeps everything in RAM and syncs with the DB for persistence.
    """

    def __init__(self):
        self.db = ChunkPlayersDB()
        # cache: {chunk_id: {user_id: {"row": int, "col": int}}}
        self._cache: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(dict)
        self._lock = threading.Lock()
        self._load_from_db()

    def _load_from_db(self):
        print("[ChunkPlayers] Loading data from DB...")
        cur = self.db.conn.execute("SELECT chunk_id, user_id, row, col FROM chunk_players")
        rows = cur.fetchall()
        for chunk_id, user_id, row, col in rows:
            self._cache[chunk_id][user_id] = {"row": row, "col": col}
        print(f"[ChunkPlayers] Loaded {len(rows)} players into memory.")

    def _save(self, chunk_id: str, user_id: str, row: int, col: int):
        self.db.add_player(chunk_id, user_id, row, col)

    def _delete(self, chunk_id: str, user_id: str):
        self.db.remove_player(chunk_id, user_id)

   
    def add_player(self, chunk_id: str, user_id: str, row: int, col: int):
        """Add or update player position in chunk."""
        with self._lock:
            self._cache[chunk_id][user_id] = {"row": row, "col": col}
            self._save(chunk_id, user_id, row, col)
            print(f"[ChunkPlayers] Added player {user_id} at ({row},{col}) in {chunk_id}")

    def update_position(self, chunk_id: str, user_id: str, row: int, col: int):
        """Update player's position inside the same chunk."""
        with self._lock:
            if user_id in self._cache.get(chunk_id, {}):
                self._cache[chunk_id][user_id] = {"row": row, "col": col}
                self._save(chunk_id, user_id, row, col)
                print(f"[ChunkPlayers] Updated player {user_id} position -> ({row},{col}) in {chunk_id}")

    def remove_player(self, chunk_id: str, user_id: str):
        """Remove player from chunk."""
        with self._lock:
            if user_id in self._cache.get(chunk_id, {}):
                del self._cache[chunk_id][user_id]
                if not self._cache[chunk_id]:
                    del self._cache[chunk_id]
                self._delete(chunk_id, user_id)
                print(f"[ChunkPlayers] Removed player {user_id} from {chunk_id}")

    def move_player(self, old_chunk: str, new_chunk: str, user_id: str, row: int, col: int):
        """Move player between chunks (with new position)."""
        if old_chunk == new_chunk:
            return self.update_position(new_chunk, user_id, row, col)

        with self._lock:
            if user_id in self._cache.get(old_chunk, {}):
                del self._cache[old_chunk][user_id]
                self._delete(old_chunk, user_id)
                if not self._cache[old_chunk]:
                    del self._cache[old_chunk]

            self._cache[new_chunk][user_id] = {"row": row, "col": col}
            self._save(new_chunk, user_id, row, col)
            print(f"[ChunkPlayers] Moved {user_id} from {old_chunk} -> {new_chunk} ({row},{col})")

    def get_players_in_chunk(self, chunk_id: str) -> List[Dict[str, int]]:
        """Return list of players with positions in a chunk."""
        return [
            {"id": uid, "row": info["row"], "col": info["col"]}
            for uid, info in self._cache.get(chunk_id, {}).items()
        ]

    def get_position(self, chunk_id: str, user_id: str):
        """Return player's (row, col) position."""
        return self._cache.get(chunk_id, {}).get(user_id)

    def remove_player_from_all(self, user_id: str):
        """Remove a player from all chunks (disconnect)."""
        with self._lock:
            for chunk_id in list(self._cache.keys()):
                if user_id in self._cache[chunk_id]:
                    del self._cache[chunk_id][user_id]
                    self._delete(chunk_id, user_id)
                    if not self._cache[chunk_id]:
                        del self._cache[chunk_id]
            print(f"[ChunkPlayers] Cleared player {user_id} from all chunks")

    def close(self):
        self.db.close()

    def is_cell_free(self, chunk_id: str, row, col) -> None:
        users = self._cache[chunk_id]
        print(users)
        for key in users:
            print("the row and col",key)
            print("-----",users[key]["row"])
            if users[key]["row"] == row and users[key]["col"]==col:
                return False
        return True
            
            