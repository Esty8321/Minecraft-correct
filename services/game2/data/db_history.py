import json, time, torch,shutil
from pathlib import Path
from datetime import datetime

from ..core.settings import HISTORY_JSON_PATH
from ..hub.types import MOVE_TOKENS, ActionToken
##pass it to the file of the settings
HISTORY_DIR = HISTORY_JSON_PATH.parent
SNAPSHOT_DIR = HISTORY_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents= True, exist_ok= True)
ACTIONS_LOG = HISTORY_DIR / "actions.jsonl"
    
    
class PlayerActionHistory:
    def __init__(self, base_path: Path = HISTORY_JSON_PATH):
        self.base_path = base_path
        self.log_file = ACTIONS_LOG
        self.snapshot_dir = SNAPSHOT_DIR
        self.snapshot_dir.mkdir(parents= True, exist_ok=True)
        
        
    def _timestamp(self) -> str:
        return datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]

    
    def _snapshot_path(self, player_id: str, chunk_id: str, ts: str)-> Path:
        """Create route for the file"""
        return self.snapshot_dir / f"{ts}_{player_id}_{chunk_id}.pt"
    
    
    def append_player_action(
        self,
        player_id:str, chunk_id: str, token: ActionToken | int, board: torch.Tensor, players: list[dict] | None = None
    ) -> None:
        ts = self._timestamp()
        snapshot_path = self._snapshot_path(player_id, chunk_id, ts)
        torch.save(board, snapshot_path)
        
        log_entry = {
            "ts": ts,
            "player_id": player_id,
            "chunk_id": chunk_id,
            "token": int(token),
            "snapshot_path": str(snapshot_path),
            "players": players or [],
        }
        
        self.log_file.parent.mkdir(parents= True, exist_ok= True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    
    def record_player_send_message(self, user_id:str,chunk_id: str, board: torch.Tensor, players):
        token = ActionToken.DM
        try:
            self.append_player_action(user_id, chunk_id, token, board, players)
        except Exception as e:
             print(f"[WARN] Failed to record send message for {user_id}: {e}")
    
            
    def record_player_action(self, user_id: str,
                                    chunk_id: str, dr: int, dc: int, board: torch.Tensor, players): 
        token = MOVE_TOKENS.get((dr, dc))
        if not token:
            return
        try:
            self.append_player_action(user_id, chunk_id,token, board, players)
        except Exception as e:
             print(f"[WARN] Failed to record action for {user_id}: {e}")
           



