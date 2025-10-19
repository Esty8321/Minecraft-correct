import json, os
from json import JSONDecodeError
from ..core.settings import MESSAGES_JSON_PATH
from ..models.message import Message

def _safe_load() -> dict:
    if not MESSAGES_JSON_PATH.exists():
        return {}
    try:
        with open(MESSAGES_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (JSONDecodeError, ValueError):
        return {}

def save_message(message: Message) -> None:
    """Atomically append/replace a message at a specific (chunk,row,col)."""
    messages = _safe_load()
    key = f"{message.chunk_id}_{message.position[0]}_{message.position[1]}"
    messages[key] = message.to_dict()

    tmp = MESSAGES_JSON_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    os.replace(tmp, MESSAGES_JSON_PATH)

def load_message(chunk_id: str, row: int, col: int) -> dict | None:
    messages = _safe_load()
    return messages.get(f"{chunk_id}_{row}_{col}")
