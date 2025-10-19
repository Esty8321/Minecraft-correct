import os, json, time
from enum import IntEnum
from json import JSONDecodeError
from ..core.settings import HISTORY_JSON_PATH

class ActionToken(IntEnum):
    RIGHT = 1
    LEFT  = 2
    UP    = 3
    DOWN  = 4
    COLOR = 5
    DM    = 6
    SLEEP_1S = 7
    SLEEP_1M = 8
    SLEEP_1H = 9

def _safe_load() -> dict:
    if not HISTORY_JSON_PATH.exists():
        return {}
    try:
        with open(HISTORY_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (JSONDecodeError, ValueError):
        return {}

def _atomic_write(payload: dict) -> None:
    HISTORY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_JSON_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    # נסה להחליף – אם ננעל, נסה כמה פעמים קצרות
    for _ in range(5):
        try:
            os.replace(tmp, HISTORY_JSON_PATH)
            return
        except PermissionError:
            time.sleep(0.1)
    raise

def _append_sleep_tokens(actions: list[int], delta_seconds: int) -> None:
    if delta_seconds <= 0: return
    hours, rem  = divmod(delta_seconds, 3600)
    minutes, sec = divmod(rem, 60)
    actions.extend([ActionToken.SLEEP_1H] * hours)
    actions.extend([ActionToken.SLEEP_1M] * minutes)
    actions.extend([ActionToken.SLEEP_1S] * sec)

def append_player_action(player_id: str, chunk_id: str, token: ActionToken, now_ts: int | None = None) -> None:
    now_ts = now_ts or int(time.time())
    data = _safe_load()
    pdata = data.setdefault(player_id, {})
    chunks = pdata.setdefault("chunks", {})
    cdata  = chunks.setdefault(chunk_id, {"actions": [], "last_ts": None})

    last_ts = cdata.get("last_ts")
    if isinstance(last_ts, int):
        delta = max(0, now_ts - last_ts)
        _append_sleep_tokens(cdata["actions"], delta)

    cdata["actions"].append(int(token))
    if len(cdata["actions"]) > 1000:
        cdata["actions"] = cdata["actions"][-1000:]

    cdata["last_ts"] = now_ts
    _atomic_write(data)
