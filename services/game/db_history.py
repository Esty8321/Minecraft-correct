# services/shared/db_history.py
import os, json, time
from json import JSONDecodeError
from pathlib import Path

BASE_ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parents[1]  # תקני בהתאם למבנה שלך
HISTORIES_JSON_PATH = BASE_ROOT_DIR / "data" / "history.json"

# === מיפוי טוקנים ===
TOKEN_RIGHT = 1
TOKEN_LEFT  = 2
TOKEN_UP    = 3
TOKEN_DOWN  = 4
TOKEN_COLOR = 5
TOKEN_DM    = 6     # הודעת צ'אט פרטית (Direct Message)
TOKEN_SLEEP_1S = 7
TOKEN_SLEEP_1M = 8
TOKEN_SLEEP_1H = 9

def _safe_load_histories() -> dict:
    if not HISTORIES_JSON_PATH.exists():
        return {}
    try:
        with open(HISTORIES_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (JSONDecodeError, ValueError):
        return {}

def _atomic_write_histories(payload: dict) -> None:
    HISTORIES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = HISTORIES_JSON_PATH.with_suffix(".tmp")
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, HISTORIES_JSON_PATH)

def _append_sleep_tokens(actions: list[int], delta_seconds: int) -> None:
    if delta_seconds <= 0:
        return
    hours = delta_seconds // 3600
    rem   = delta_seconds % 3600
    minutes = rem // 60
    seconds = rem % 60
    actions.extend([TOKEN_SLEEP_1H] * hours)
    actions.extend([TOKEN_SLEEP_1M] * minutes)
    actions.extend([TOKEN_SLEEP_1S] * seconds)

def append_player_action(player_id: str, chunk_id: str, action_token: int, now_ts: int | None = None) -> None:

    now_ts = now_ts or int(time.time())
    data = _safe_load_histories()
    pdata = data.setdefault(player_id, {})
    chunks = pdata.setdefault("chunks", {})
    cdata = chunks.setdefault(chunk_id, {"actions": [], "last_ts": None})

    last_ts = cdata.get("last_ts")
    if isinstance(last_ts, int):
        delta = max(0, now_ts - last_ts)
        _append_sleep_tokens(cdata["actions"], delta)

    cdata["actions"].append(int(action_token))
    if len(cdata["actions"]) > 1000:
        cdata["actions"] = cdata["actions"][-1000:]
    cdata["last_ts"] = now_ts
    _atomic_write_histories(data)
