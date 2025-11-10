from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import time
from typing import Literal, Dict, Any, Optional

ActionName = Literal["LEFT","RIGHT","UP","DOWN","COLOR"]

@dataclass
class UserActionLogger:
    root: Path

    def __post_init__(self):
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _action_name(token: int) -> ActionName:
        mapping = {
            1: "RIGHT",
            2: "LEFT",
            3: "UP",
            4: "DOWN",
            5: "COLOR",
        }
        return mapping[int(token)]

    def _file(self, user_id: str) -> Path:
        d = self.root / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d / "actions.jsonl"

    def append(self,
               user_id: str,
               chunk_id: str,
               row: int,
               col: int,
               token: int,
               extra: Optional[Dict[str, Any]] = None) -> None:
        p = self._file(user_id)
        rec = {
            "ts": time.time(),
            "user_id": user_id,
            "chunk_id": chunk_id,
            "row": int(row),
            "col": int(col),
            "action": self._action_name(token),
            "token": int(token),
        }
        if extra:
            rec.update(extra)

        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
