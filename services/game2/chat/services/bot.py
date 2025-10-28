# from __future__ import annotations

# from datetime import datetime
# from typing import List, Optional

# import httpx

# from ..config import MODEL_SERVER_URL, BOT_ORIGIN, BOT_MODEL
# from ..storage.json_store import players_data, chats_data, save_json, CHATS_PATH
# from ..services.messages import history_between, unread_count_for, minimal_view
# from ..services.presence import send_to_all


# def _append_message_bot(fr: str, to: str, text: str, ts: Optional[str] = None) -> dict:
#     ts = ts or (datetime.utcnow().isoformat() + "Z")
#     msg = {
#         "id": f"{ts}|{fr}|{text}",
#         "from": fr,
#         "to": to,
#         "message": text or "",
#         "timestamp": ts,
#         "quoted_id": None,
#         "reactions": {},
#         "read_by": [],            
#         "deleted": False,
#         "origin": BOT_ORIGIN,
#         "model": BOT_MODEL,
#     }
#     chats_data["chats"][0]["messages"].append(msg)
#     save_json(CHATS_PATH, chats_data)
#     return msg


# async def _call_model_generate(turns: List[dict]) -> List[str]:
#     try:
#         async with httpx.AsyncClient(timeout=30.0) as client:
#             r = await client.post(
#                 f"{MODEL_SERVER_URL}/generate",
#                 json={
#                     "messages": turns,
#                     "max_new_tokens": 1024,
#                     "temperature": 0.7,  
#                 },
#             )
#         r.raise_for_status()
#         data = r.json()
#         if isinstance(data, dict) and isinstance(data.get("text"), str):
#             return [data["text"]]
#         return []
#     except Exception:
#         return []


# def _build_turns(sender: str, receiver: str) -> List[dict]:
   
#     raw = history_between(receiver, sender)  

#     turns: List[dict] = [{
#         "role": "system",
#         "content": f"Respond succinctly and naturally as '{sender}'. Keep a friendly tone."
#     }]

#     for m in raw:
#         if m.get("deleted"):
#             continue
#         txt = (m.get("message") or "").strip()
#         if not txt:
#             continue
#         role = "assistant" if m.get("from") == sender else "user"
#         if turns and turns[-1]["role"] == role and role != "system":
#             turns[-1]["content"] += "\n" + txt
#         else:
#             turns.append({"role": role, "content": txt})

#     first_idx = 0
#     while first_idx < len(turns) and turns[first_idx]["role"] == "system":
#         first_idx += 1
#     if first_idx >= len(turns) or turns[first_idx]["role"] != "user":
#         turns.insert(first_idx, {"role": "user", "content": "Hi"})

#     compact: List[dict] = []
#     for t in turns:
#         if compact and compact[-1]["role"] == t["role"] and t["role"] != "system":
#             compact[-1]["content"] += "\n" + t["content"]
#         else:
#             compact.append(t)
#     turns = compact

#     if turns[-1]["role"] != "user":
#         turns.append({"role": "user", "content": "Continue."})

#     return turns


# async def handle_bot_send(
#     on_behalf_of: str,
#     to: str,
#     mode: str = "generate",
#     text: Optional[str] = None,
#     system_hint: Optional[str] = None,
# ):
#     known = {p.get("id") or p.get("player_id") or p.get("name") for p in players_data.get("players", [])}
#     if on_behalf_of not in known or to not in known:
#         return {"ok": False, "reason": "unknown_player", "details": {"sender": on_behalf_of, "receiver": to}}

#     if mode == "use_text":
#         txt = (text or "").strip()
#         if not txt:
#             return {"ok": False, "reason": "missing_text"}
#         msg = _append_message_bot(on_behalf_of, to, txt)
#         payload = minimal_view(msg)
#         payload.update({"type": "message", "sender": on_behalf_of, "to": to})
#         await send_to_all(on_behalf_of, payload)
#         await send_to_all(to, payload)
#         await send_to_all(to, {
#             "type": "unread", "from": on_behalf_of, "to": to,
#             "count": unread_count_for(to, on_behalf_of),
#         })
#         return {"ok": True, "mode": "use_text", "message_id": msg["id"]}

#     turns = _build_turns(sender=on_behalf_of, receiver=to)
#     if system_hint:
#         turns.insert(0, {"role": "system", "content": system_hint.strip()})

#     outs = await _call_model_generate(turns)
#     if not outs:
#         return {"ok": False, "reason": "model_empty_response"}  

#     txt = outs[0].strip()
#     if not txt:
#         return {"ok": False, "reason": "empty_text_after_strip"}

#     msg = _append_message_bot(on_behalf_of, to, txt)
#     payload = minimal_view(msg)
#     payload.update({"type": "message", "sender": on_behalf_of, "to": to})
#     await send_to_all(on_behalf_of, payload)
#     await send_to_all(to, payload)
#     await send_to_all(to, {
#         "type": "unread", "from": on_behalf_of, "to": to,
#         "count": unread_count_for(to, on_behalf_of),
#     })
#     return {"ok": True, "mode": "generate", "message_id": msg["id"], "text": txt}
