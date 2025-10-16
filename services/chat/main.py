from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Optional, Set, List
from datetime import datetime
import asyncio
import json
import os
import httpx
from services.game.db_history import append_player_action, TOKEN_DM

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:7001")

# ---------- נתיבי קבצים (מוחלטים) ----------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, "data")
CHATS_PATH   = os.path.join(DATA_DIR, "chats.json")


# os.makedirs(DATA_DIR, exist_ok=True)
# if not os.path.exists(CHATS_PATH):
#     with open(CHATS_PATH, "w", encoding="utf-8") as f:
#         json.dump({"chats": [{"chat_id": "chat1", "messages": []}]}, f, ensure_ascii=False, indent=2)

# ---------- עזר לקבצי JSON ----------
def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- שליפת טוקן מהבקשה ----------
# def get_token_from_ws(ws: WebSocket) -> Optional[str]:
#     # עדיפות ל-Authorization: Bearer <token>, אחרת query ?token=
#     auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
#     if auth and auth.lower().startswith("bearer "):
#         return auth.split(" ", 1)[1].strip()
#     return ws.query_params.get("token")

# ---------- נתונים מהדיסק ----------
# players_data = load_json(PLAYERS_PATH)
DEFAULT_CHATS = {"chats": [{"chat_id": "chat1", "messages": []}]}
chats_data = load_json(CHATS_PATH) or DEFAULT_CHATS
# tokens_data = load_json(TOKENS_PATH)

# ---------- עזר מזהה ----------
def _msg_id(ts: str, fr: str, text: str) -> str:
    return f"{ts}|{fr}|{text}"

def _retrofit_messages():
    msgs: List[dict] = chats_data.get("chats", [{}])[0].get("messages", [])
    changed = False
    for m in msgs:
        # timestamp + id
        if "timestamp" not in m:
            m["timestamp"] = datetime.utcnow().isoformat() + "Z"; changed = True
        if "id" not in m:
            m["id"] = _msg_id(m["timestamp"], m.get("from",""), m.get("message","")); changed = True

        # read_by
        if "read_by" not in m or not isinstance(m.get("read_by"), list):
            sender = m.get("from")
            m["read_by"] = [sender] if sender else []
            changed = True

        # reactions (ממפה likes ישנים, אם קיימים)
        if "reactions" not in m or not isinstance(m.get("reactions"), dict):
            m["reactions"] = {}
            changed = True

        if "likes" in m:
            # likes כ-List => כולם "up" (למעט השולח)
            if isinstance(m["likes"], list):
                for pid in m["likes"]:
                    if pid and isinstance(pid, str) and pid != m.get("from"):
                        m["reactions"][pid] = "up"
                changed = True
            # likes כ-Dict עם 👍/👎
            if isinstance(m["likes"], dict):
                ups = m["likes"].get("👍", []) or []
                downs = m["likes"].get("👎", []) or []
                for pid in ups:
                    if pid and pid != m.get("from"):
                        m["reactions"][pid] = "up"
                for pid in downs:
                    if pid and pid != m.get("from"):
                        m["reactions"][pid] = "down"
                changed = True
            m.pop("likes", None); changed = True

        # quoted_id: נוודא טיפוס תקין אם קיים
        if "quoted_id" in m and not isinstance(m.get("quoted_id"), (str, type(None))):
            m["quoted_id"] = None
            changed = True

        # מחיקה רכה: דגל ברירת מחדל
        if "deleted" not in m:
            m["deleted"] = False
            changed = True

        # טקסט חייב להיות string
        if "message" in m and m["message"] is None:
            m["message"] = ""
            changed = True

    if changed:
        save_json(CHATS_PATH, chats_data)

_retrofit_messages()

# מיפוי מהיר: token -> player_id
# TOKEN_TO_PLAYER: Dict[str, str] = {t["token"]: t["player_id"] for t in tokens_data.get("tokens", [])}

# ---------- מצבי ריצה ----------
active_players: Dict[str, Set[WebSocket]] = {}   # לכל שחקן: סט WebSockets (כמה טאבים)
selected_partner: Dict[str, Optional[str]] = {}  # מי הנמען שנבחר בכל רגע

# ---------- אפליקציה ----------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------- עזרי לוגיקה ----------
def get_message_by_id(msg_id: str) -> Optional[dict]:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    for m in msgs:
        mid = m.get("id") or _msg_id(m.get("timestamp",""), m.get("from",""), m.get("message",""))
        if mid == msg_id:
            m.setdefault("id", mid)
            m.setdefault("reactions", {})
            m.setdefault("read_by", [m.get("from")] if m.get("from") else [])
            m.setdefault("deleted", False)
            if "quoted_id" in m and not isinstance(m.get("quoted_id"), (str, type(None))):
                m["quoted_id"] = None
            return m
    return None

def append_message(fr: str, to: str, text: str, ts: Optional[str] = None, quoted_id: Optional[str] = None) -> dict:
    ts = ts or datetime.utcnow().isoformat() + "Z"
    msg = {
        "id": _msg_id(ts, fr, text),
        "from": fr,
        "to": to,
        "message": text,
        "timestamp": ts,
        "quoted_id": quoted_id or None,  # ← תמיכה בציטוט
        "reactions": {},
        "read_by": [fr],
        "deleted": False,
    }
    chats_data["chats"][0]["messages"].append(msg)
    save_json(CHATS_PATH, chats_data)
    return msg

def _minimal_view(m: dict, viewer: Optional[str] = None) -> dict:
    """תצוגה מינימלית ללקוח. לא חושפת את כל reactions, רק my_reaction של הצופה."""
    view = {
        "id": m["id"],
        "from": m["from"],
        "to": m["to"],
        "message": m.get("message", ""),
        "timestamp": m["timestamp"],
        "read_by": m.get("read_by", []),
        "deleted": m.get("deleted", False),
    }
    if m.get("quoted_id"):
        view["quotedId"] = m["quoted_id"]
        # נחזיר גם snippet בסיסי של ההודעה המצוטטת לנוחות ה-UI (כולל deleted)
        q = get_message_by_id(m["quoted_id"])
        if q:
            view["quoted_message"] = {
                "id": q["id"],
                "from": q["from"],
                "message": q.get("message", ""),
                "timestamp": q["timestamp"],
                "deleted": q.get("deleted", False),
            }
    if viewer:
        view["my_reaction"] = m.get("reactions", {}).get(viewer, None)
    return view

def history_between(a: str, b: str, viewer: Optional[str]=None) -> List[dict]:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    out: List[dict] = []
    for m in msgs:
        if (m.get("from") == a and m.get("to") == b) or (m.get("from") == b and m.get("to") == a):
            m.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
            m.setdefault("id", _msg_id(m["timestamp"], m.get("from",""), m.get("message","")))
            m.setdefault("reactions", {})
            m.setdefault("read_by", [m.get("from")] if m.get("from") else [])
            m.setdefault("deleted", False)
            if "quoted_id" in m and not isinstance(m.get("quoted_id"), (str, type(None))):
                m["quoted_id"] = None
            out.append(_minimal_view(m, viewer))
    return out

def unread_count_for(me: str, from_id: str) -> int:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    return sum(1 for m in msgs if m.get("from") == from_id and m.get("to") == me and me not in m.get("read_by", []))

def mark_read_pair(me: str, with_id: str) -> int:
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    updated = 0
    for m in msgs:
        if m.get("from") == with_id and m.get("to") == me:
            rb = m.setdefault("read_by", [])
            if me not in rb:
                rb.append(me)
                updated += 1
    if updated:
        save_json(CHATS_PATH, chats_data)
    return updated

async def _send_to_all(player_id: str, payload: dict):
    for s in list(active_players.get(player_id, set())):
        await s.send_text(json.dumps(payload))

# ---------- NEW: מחיקה רכה ----------
def soft_delete_message_by_id(message_id: str, requester_id: str) -> Optional[dict]:
    """
    מסמן הודעה כמחוקה רכה (deleted=True, message="")
    רק אם requester_id הוא השולח של ההודעה.
    מחזיר את ההודעה המעודכנת או None אם לא נמצא/אין הרשאה.
    """
    msgs = chats_data.get("chats", [{}])[0].get("messages", [])
    for m in msgs:
        if (m.get("id") or "") == message_id:
            if m.get("from") != requester_id:
                return None
            if not m.get("deleted", False):
                m["deleted"] = True
                m["message"] = ""  # לא שומרים תוכן אחרי מחיקה רכה
                m["updated_at"] = datetime.utcnow().isoformat() + "Z"
                save_json(CHATS_PATH, chats_data)
            return m
    return None

def chat_participants_of(m: dict) -> List[str]:
    """מחזיר את שני הצדדים של ההודעה לשידור עדכון."""
    a = m.get("from"); b = m.get("to")
    return [pid for pid in [a, b] if pid]



async def get_players_from_auth():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{AUTH_SERVICE_URL}/players")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("players", [])
            else:
                print(f"[CHAT] Failed to fetch players: {resp.status_code}")
                return []
    except Exception as e:
        print(f"[CHAT] Error fetching players:", e)
        return []
    
# ---------- REST ----------
@app.get("/active-players")
async def get_active_players():
    players = await get_players_from_auth()
    result = []
    for p in players:
        pid = p.get("id") or p.get("player_id") or p.get("name")
        result.append({**p, "is_connected": bool(active_players.get(pid))})
    return result

# @app.get("/whoami")
# async def whoami(token: str):
#     pid = TOKEN_TO_PLAYER.get(token)
#     if not pid:
#         return JSONResponse({"ok": False, "reason": "invalid_token"}, status_code=401)
#     return {"ok": True, "player_id": pid}

@app.get("/history")
async def get_history(a: str, b: str):
    if not a or not b:
        print("there is something that missing in the history --")
        return JSONResponse({"ok": False, "reason": "invalid_token"}, status_code=401)
    return {"ok": True, "messages": history_between(a, b, viewer=a)}

@app.get("/unread-summary")
async def unread_summary(me: str):
    """מחזיר מפה של כמות הודעות לא־נקראות לכל פרטנר -> count."""
    players = await get_players_from_auth()
    # אוספים כל מי ששלח אליי פעם (או קיים ברשימת players)
    peers = {m["from"] for m in chats_data.get("chats", [{}])[0].get("messages", []) if m.get("to") == me}
    for p in players:
        pid = p.get("id") or p.get("player_id") or p.get("name")
        if pid != me:
            peers.add(pid)
    counts = {pid: unread_count_for(me, pid) for pid in peers if pid and pid != me}
    return {"ok": True, "counts": counts}

# ---------- WebSocket ----------
@app.websocket("/ws")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        init_raw = await websocket.receive_text()
        init = json.loads(init_raw)
        player_id = init.get("player_id")
        if not player_id or not isinstance(player_id, str):
            await websocket.send_text(json.dumps({"type":"error", "message":"missing player_id"}))
            await websocket.close(code=4401)
            return
    except Exception:
        await websocket.close(code=4401)
        return 
    active_players.setdefault(player_id, set()).add(websocket)
    selected_partner[player_id] = None
    print(f"[WS] {player_id} connected")
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            typ = (data.get("type") or "").lower()
            # בחירת בן-שיחה -> נחזיר היסטוריה + נאפס unread מולו
            if typ == "select":
                selected_partner[player_id] = data.get("selectedPlayer")
                partner = selected_partner[player_id]
                if partner:
                    msgs = history_between(player_id, partner, viewer=player_id)
                    await websocket.send_text(json.dumps({
                        "type": "history",
                        "with": partner,
                        "messages": msgs
                    }))
                    # אחרי הצגת היסטוריה – נסמן כנקראו
                    changed = mark_read_pair(player_id, partner)
                    if changed:
                        count_now = unread_count_for(player_id, partner)
                        await _send_to_all(player_id, {
                            "type": "unread", "from": partner, "to": player_id, "count": count_now
                        })
                continue

            # סימון קריאה מפורש
            if typ == "read":
                partner = data.get("with")
                if partner:
                    mark_read_pair(player_id, partner)
                    count_now = unread_count_for(player_id, partner)
                    await _send_to_all(player_id, {
                        "type": "unread", "from": partner, "to": player_id, "count": count_now
                    })
                continue

            # אינדיקציית הקלדה
            if typ == "typing":
                partner = selected_partner[player_id]
                if partner:
                    await _send_to_all(partner, {"type": "typing", "typing": [player_id]})
                continue

            # תגובה פרטית (ACK רק למגיב)
            if typ == "react":
                # payload: { type: "react", messageId: "...", reaction: "up" | "down" | None }
                msg_id = data.get("messageId")
                reaction = data.get("reaction")  # "up" | "down" | None
                if not msg_id:
                    await websocket.send_text(json.dumps({"type": "error", "message": "missing messageId"}))
                    continue

                msg_obj = get_message_by_id(msg_id)
                if not msg_obj:
                    await websocket.send_text(json.dumps({"type": "error", "message": "message not found"}))
                    continue

                # לא מגיבים להודעה שלי
                if msg_obj.get("from") == player_id:
                    await websocket.send_text(json.dumps({"type": "error", "message": "cannot react to own message"}))
                    continue

                msg_obj.setdefault("reactions", {})
                if reaction in ("up", "down"):
                    msg_obj["reactions"][player_id] = reaction
                else:
                    # ביטול
                    msg_obj["reactions"].pop(player_id, None)

                save_json(CHATS_PATH, chats_data)

                # ACK פרטי – כולל my_reaction
                await websocket.send_text(json.dumps({
                    "type": "react",
                    "messageId": msg_id,
                    "my_reaction": reaction
                }))
                continue

            # שליחת הודעה (עם quotedId אופציונלי)
            if typ == "message":
                text = data.get("message", "")
                partner = data.get("selectedPlayer") or selected_partner.get(player_id)
                quoted_id = data.get("quotedId") or data.get("quoted_id")
                if not partner:
                    await websocket.send_text(json.dumps({"type": "error", "message": "No partner selected"}))
                    continue

                saved = append_message(player_id, partner, text, data.get("timestamp"), quoted_id=quoted_id)


                chunk_id = data.get("chunkId")  # ← מגיע מהקליינט בצ'אט הפרטי
                if isinstance(chunk_id, str) and chunk_id:
                    try:
                        append_player_action(player_id, chunk_id, TOKEN_DM)
                    except Exception as e:
                        print(f"[CHAT] Failed to append DM action for {player_id} on {chunk_id}: {e}")
                else:
                    print(f"[CHAT] DM without chunkId from {player_id}; history not recorded")


                # payload לכולם (כולל שדות תצוגה ומידע על הציטוט)
                msg_payload = _minimal_view(saved)  # כולל quotedId + quoted_message snippet אם אפשר
                msg_payload.update({
                    "type": "message",
                    "sender": player_id,
                    "to": partner,
                    "isBot": False
                })

                # שידור לכל הטאבים של השולח והנמען
                await _send_to_all(player_id, msg_payload)
                await _send_to_all(partner,   msg_payload)

                # אישור ספציפי לשולח (לא חובה)
                await websocket.send_text(json.dumps({
                    "type": "sent",
                    "to": partner,
                    "id": saved["id"],
                    "message": text,
                    "timestamp": saved["timestamp"]
                }))

                # עדכון מונה לנמען
                new_count = unread_count_for(partner, player_id)
                await _send_to_all(partner, {"type": "unread", "from": player_id, "to": partner, "count": new_count})
                continue

            # NEW: מחיקה רכה של הודעה (delete / DELETE)
            if typ == "delete":
                # payload: { type: "delete", messageId: "<id>" }
                msg_id = data.get("messageId") or data.get("message_id")
                if not msg_id:
                    await websocket.send_text(json.dumps({"type": "error", "message": "missing messageId"}))
                    continue

                updated = soft_delete_message_by_id(msg_id, requester_id=player_id)
                if not updated:
                    await websocket.send_text(json.dumps({"type": "error", "message": "delete_not_allowed_or_not_found", "messageId": msg_id}))
                    continue

                # שידור עדכון לשני הצדדים
                payload = {
                    "type": "message_updated",
                    "message": {
                        "id": updated["id"],
                        "from": updated.get("from"),
                        "to": updated.get("to"),
                        "deleted": True,
                        "text": "",
                        "updated_at": updated.get("updated_at"),
                    }
                }
                for pid in chat_participants_of(updated):
                    await _send_to_all(pid, payload)

                # ACK אופציונלי
                # await websocket.send_text(json.dumps({"type": "ack", "op": "delete", "messageId": msg_id}))
                continue

            # לא מזוהה
            await websocket.send_text(json.dumps({"type": "error", "message": f"unknown type: {typ}"}))

    except WebSocketDisconnect:
        pass
    finally:
        # ניקוי חיבורים
        try:
            bucket = active_players.get(player_id)
            if bucket:
                bucket.discard(websocket)
                if not bucket:
                    active_players.pop(player_id, None)
        except Exception:
            pass

        selected_partner[player_id] = None
        print(f"[WS] {player_id} disconnected")

# ---------- תחזוקה (דמו) ----------
async def heartbeat():
    while True:
        await asyncio.sleep(60)
        if active_players:
            print("[HEARTBEAT] active:", list(active_players.keys()))

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(heartbeat())
