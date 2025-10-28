from datetime import datetime
import uuid

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def make_message_id() -> str:
    return uuid.uuid4().hex

def msg_id(ts: str, fr: str, text: str) -> str:
    return f"{ts}|{fr}|{text}"
