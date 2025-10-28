
import json, os, asyncio
from json import JSONDecodeError
from pathlib import Path
from ..core.settings import SCROLLS_JSON_PATH
from ..hub.scroll_message import ScrollMessage

class ScrollDB:
    def __init__(self, path: Path =SCROLLS_JSON_PATH, authosave_interval: int = 10):
        self.path = Path(path)
        self._scrolls: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self.anutosave_interval = authosave_interval
        
        if self.path.exists():
            try:
                with open(self.path, "r", encoding= "utf-8") as f:
                    self._scrolls = json.load(f)
                print(f"[ScrollDB] Loaded {len(self._scrolls)} scrolls from disk.")
            except Exception as e:
                print(f"[ScrollDB] Failed to load scrolls: {e}")
        asyncio.create_task(self._autosave_loop())

    async def save_scroll(self, scroll: ScrollMessage) -> None:
        """Save or replace a message in memory, disk will update automatically."""
        key = f"{scroll.chunk_id}_{scroll.position[0]}_{scroll.position[1]}"
        async  with self._lock:
            self._scrolls[key] = scroll.to_dict()
            
    async def load_scroll(self, chunk_id: str, row:int, col: int)->str | None:
        """Load a scroll message directly from memory."""
        key = f"{chunk_id}_{row}_{col}"
        return self._scrolls.get(key)
    
    
    async def _autosave_loop(self):
        """Background task that saves all scrolls to disk periodically."""
        while True:
            await asyncio.sleep(self.anutosave_interval)
            await self.save_to_disk()
    
    
    async def save_to_disk(self):
        """Write in-memory scrolls to disk safely."""    
        async with self._lock:
            try:
                self.path.parent.mkdir(parents= True, exist_ok= True)
                tmp = self.path.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._scrolls, f, indent= 2, ensure_ascii= False)
                tmp.replace(self.path)
                print(f"[ScrollDB] Saved {len(self._scrolls)} scrolls to disk.")
            except Exception as e:
                 print(f"[ScrollDB] Failed to save scrolls: {e}")
               