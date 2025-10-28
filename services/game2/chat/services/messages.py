from __future__ import annotations
from typing import List, Optional, Dict
from datetime import datetime
from ..storage.json_store import chats_data, save_json, CHATS_PATH
from ..utils.time_ids import msg_id as _msg_id

def minimal_view(m: dict, viewer: Optional[str]=None) -> dict:
    v = {
        "id": m["id"],
        "from": m["from"],
        "to": m["to"],
        "message": m.get("message", ""),
        "timestamp": m["timestamp"],
        "read_by": m.get("read_by", []),
        "deleted": m.get("deleted", False),
    }
    if m.get("quoted_id"):
        v["quotedId"] = m["quoted_id"]
    if viewer:
        v["my_reaction"] = m.get("reactions", {}).get(viewer)
    return v

def get_message_by_id(mid: str) -> Optional[dict]:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    for m in msgs:
        if (m.get("id") or "") == mid:
            return m
    return None

def append_message(fr: str, to: str, text: str, ts: Optional[str]=None, quoted_id: Optional[str]=None) -> dict:
    ts = ts or datetime.utcnow().isoformat() + "Z"
    msg = {
        "id": _msg_id(ts, fr, text),
        "from": fr,
        "to": to,
        "message": text or "",
        "timestamp": ts,
        "quoted_id": quoted_id or None,
        "reactions": {},
        "read_by": [fr],
        "deleted": False,
        "origin": None,
        "model": None,
    }
    chats_data["chats"][0]["messages"].append(msg)
    save_json(CHATS_PATH, chats_data)
    return msg

def history_between(a: str, b: str, viewer: Optional[str]=None) -> List[dict]:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    out: List[dict] = []
    for m in msgs:
        if (m.get("from")==a and m.get("to")==b) or (m.get("from")==b and m.get("to")==a):
            m.setdefault("timestamp", datetime.utcnow().isoformat()+"Z")
            m.setdefault("id", _msg_id(m["timestamp"], m.get("from",""), m.get("message","")))
            m.setdefault("reactions", {})
            m.setdefault("read_by", [m.get("from")] if m.get("from") else [])
            m.setdefault("deleted", False)
            m.setdefault("origin", None)
            m.setdefault("model", None)
            out.append(minimal_view(m, viewer))
    return out[-128:] 

def unread_count_for(me: str, from_id: str) -> int:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    return sum(
        1 for m in msgs
        if m.get("from")==from_id and m.get("to")==me and me not in m.get("read_by", [])
    )

def mark_read_pair(me: str, with_id: str) -> int:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    updated = 0
    for m in msgs:
        if m.get("from")==with_id and m.get("to")==me:
            rb = m.setdefault("read_by", [])
            if me not in rb:
                rb.append(me)
                updated += 1
    if updated:
        save_json(CHATS_PATH, chats_data)
    return updated

def unread_summary_for(me: str) -> Dict[str, int]:
    peers = set()
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    for m in msgs:
        if m.get("to")==me:
            peers.add(m.get("from"))
    return {pid: unread_count_for(me, pid) for pid in peers if pid and pid != me}

def soft_delete_message_by_id(message_id: str, requester_id: str) -> Optional[dict]:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    for m in msgs:
        if (m.get("id") or "") == message_id:
            if m.get("from") != requester_id:
                return None
            if not m.get("deleted", False):
                m["deleted"] = True
                m["message"] = ""
                m["updated_at"] = datetime.utcnow().isoformat()+"Z"
                save_json(CHATS_PATH, chats_data)
            return m
    return None
