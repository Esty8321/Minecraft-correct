import os, json, time
from enum import IntEnum
from json import JSONDecodeError
from typing import Any
import torch
import numpy as np
from datetime import datetime
from pathlib import Path

from ..core.settings import HISTORY_JSON_PATH

HISTORY_INDEX_PATH: Path = HISTORY_JSON_PATH
HISTORY_LOG_PATH: Path = HISTORY_JSON_PATH.with_suffix(".jsonl")

class ActionToken(IntEnum):
    RIGHT = 1
    LEFT = 2
    UP = 3
    DOWN = 4
    COLOR = 5
    DM = 6

class PlayerActionHistory:
    """Records and stores player actions for analysis and model training."""
    def __init__(self, base_path: Path = HISTORY_JSON_PATH):
        self.index_path: Path = base_path
        self.log_path: Path = base_path.with_suffix(".jsonl")
         
    def _safe_load(self) -> dict:
        """Load the Json index file safely"""
        if self.index_path.exists():
            return {}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (JSONDecodeError, ValueError):
            return {}

    def _atomic_write(self, payload: dict) -> None:
        """Write Json file atomically"""
        self.index_path.parent.mkdir(parents= True, exist_ok=True)
        tmp = self.index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        for _ in range(5):
            try:
                os.replace(tmp, self.index_path)
                return
            except PermissionError:
                time.sleep(0.1)
        raise RuntimeError("Failed to write history Json file atomically.")

    @staticmethod
    def _to_int_list(board_state: Any) -> list[int]:
        """Normalize various board representations to int list"""
        try:
            if isinstance(board_state, torch.Tensor):
                return (
                    board_state.detach().cpu().numpy().astype(int).ravel().tolist()
                )
        except Exception:
            pass

        try:
            if isinstance(board_state, np.ndarray):
                return board_state.astype(int).ravel().tolist()
        except Exception:
            pass

        if isinstance(board_state, list):
            if len(board_state) > 0 and isinstance(board_state[0], list):
                flat: list[int] = []
                for row in board_state:
                    flat.extend(int(x) for x in row)
                return flat
            return [int(x) for x in board_state]

        if isinstance(board_state, (bytes, bytearray)):
            return [int(b) for b in board_state]

        return [int(board_state)]


    def append_player_action(
       self,
       player_id: str,
       chunk_id: str,
       token: ActionToken | int,
       board_state: Any,
       now_ts: int | None = None,
      ) -> None:
        """Append a player action to the Json index and the log file"""
        ts = now_ts or int(time.time())
        ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

        action_entry = {
            "ts": ts_str,
            "token": int(token),
            "board": json.dumps(self._to_int_list(board_state), separators=(",", ":")),
        }

        data = self._safe_load()
        pdata = data.setdefault(player_id, {})
        chunks = pdata.setdefault("chunks", {})
        cdata = chunks.setdefault(chunk_id, {"actions": [], "last_ts": None})
        cdata["actions"].append(action_entry)
        cdata["last_ts"] = ts_str
        self._atomic_write(data)

        log_entry = {"player_id": player_id, "chunk_id": chunk_id, **action_entry}
        HISTORY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            
            
    async def record_player_action(self, user_id: str, chunk_id: str, dr: int, dc: int, board):
        from ..hub.types import MOVE_TOKENS
        token = MOVE_TOKENS.get((dr, dc))
        if not token:
            return
        try:
            self.append_player_action(user_id, chunk_id, token, board)
        except Exception:
            pass

