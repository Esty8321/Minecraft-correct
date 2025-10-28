from pathlib import Path
import json
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR_CANDIDATES = [ROOT_DIR / "Data", ROOT_DIR / "data"]
for _cand in DATA_DIR_CANDIDATES:
    if _cand.exists():
        DATA_DIR = _cand
        break
else:
    DATA_DIR = ROOT_DIR / "data"

PLAYERS_PATH = DATA_DIR / "players.json"
CHATS_PATH   = DATA_DIR / "chats.json"
TOKENS_PATH  = DATA_DIR / "tokens.json"

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

players_data = load_json(PLAYERS_PATH)
DEFAULT_CHATS = {"chats": [{"chat_id": "chat1", "messages": []}]}
chats_data = load_json(CHATS_PATH) or DEFAULT_CHATS
tokens_data = load_json(TOKENS_PATH)

TOKEN_TO_PLAYER = {t.get("token"): t.get("player_id") for t in tokens_data.get("tokens", []) if t.get("token")}

def save_chats():
    save_json(CHATS_PATH, chats_data)

def retrofit_messages():
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    changed = False
    for m in msgs:
        if "timestamp" not in m:
            m["timestamp"] = datetime.utcnow().isoformat() + "Z"; changed = True
        if "id" not in m:
            ts = m.get("timestamp",""); fr = m.get("from",""); tx = m.get("message","")
            m["id"] = f"{ts}|{fr}|{tx}"; changed = True
        if "read_by" not in m or not isinstance(m.get("read_by"), list):
            sender = m.get("from"); m["read_by"] = [sender] if sender else []; changed = True
        if "reactions" not in m or not isinstance(m.get("reactions"), dict):
            m["reactions"] = {}; changed = True
        if "deleted" not in m:
            m["deleted"] = False; changed = True
        if "message" in m and m["message"] is None:
            m["message"] = ""; changed = True
        m.setdefault("origin", None)
        m.setdefault("model",  None)
        if "quoted_id" in m and not isinstance(m.get("quoted_id"), (str, type(None))):
            m["quoted_id"] = None; changed = True
    if changed:
        save_chats()

retrofit_messages()
