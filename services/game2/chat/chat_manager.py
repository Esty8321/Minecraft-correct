

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .storage.json_store import TOKEN_TO_PLAYER
from .services.messages import (
    append_message, get_message_by_id, history_between,
    mark_read_pair, unread_count_for, soft_delete_message_by_id, minimal_view
)   
from typing import Dict, Optional

from ..hub.sessions import SessionStore
   
_selected_partner: Dict[str, Optional[str]] = {}#who selectd who in the chat

def set_selected_partner(me: str, other: Optional[str]) -> None:
    _selected_partner[me] = other
    
    
def get_selected_partner(me: str) -> Optional[str]:
    return _selected_partner.get(me)



async def broadcast_to_player(session_store: SessionStore, player_id: str, payload: dict) -> None:
    """Send to all the sockets of specific player payload."""
    print("in the broadcast of the chat!!------")
    for ws in session_store.sockets_for_user(player_id).copy():
        try:
            await ws.send_json(payload)
        except Exception:
            session_store.pop(ws)
            
            
            
async def handle_chat(ws: WebSocket, kind: str, data, player_id, session_store: SessionStore):
            print("in hadle message of the chat-----")
            if kind == "select":
                partner = data.get("selectedPlayer")##??get the id of the another player
                
                set_selected_partner(player_id, partner)
                if partner:
                    msgs = history_between(player_id, partner, viewer=player_id)
                    await ws.send_json({"type": "history", "with": partner, "messages": msgs})
                    if mark_read_pair(player_id, partner):
                        await broadcast_to_player(player_id, {
                            "type": "unread", "from": partner, "to": player_id,
                            "count": unread_count_for(player_id, partner)
                        })
                return
            
            if kind == "read":
                partner = data.get("with")
                if partner:
                    mark_read_pair(player_id, partner)
                    await send_to_all(player_id, {
                        "type": "unread", "from": partner, "to": player_id,
                        "count": unread_count_for(player_id, partner)
                    })
                return

            if kind == "typing":
                partner = get_selected(player_id)
                if partner:
                    await send_to_all(partner, {"type": "typing", "typing": [player_id]})
                return

            if kind == "react":
                msg_id = data.get("messageId")
                reaction = data.get("reaction")  
                if not msg_id:
                    await ws.send_json({"type": "error", "message": "missing messageId"})
                    return

                m = get_message_by_id(msg_id)
                if not m:
                    await ws.send_json({"type": "error", "message": "message not found"})
                    return
                if m.get("from") == player_id:
                    await ws.send_json({"type": "error", "message": "cannot react to own message"})
                    return

                m.setdefault("reactions", {})
                if reaction in ("up", "down"):
                    m["reactions"][player_id] = reaction
                else:
                    m["reactions"].pop(player_id, None)

                await ws.send_json({"type": "react", "messageId": msg_id, "my_reaction": reaction})
                return
    
            if kind == "message":
                text = data.get("message", "")
                partner = data.get("selectedPlayer") or get_selected(player_id)
                quoted_id = data.get("quotedId") or data.get("quoted_id")
                if not partner:
                    await ws.send_json({"type": "error", "message": "No partner selected"})
                    return

                saved = append_message(player_id, partner, text, data.get("timestamp"), quoted_id=quoted_id)
                payload = minimal_view(saved) | {"type": "message", "sender": player_id, "to": partner}

                # await send_to_all(player_id, payload)
                # await send_to_all(partner, payload)
                await broadcast_to_player(session_store, player_id, payload)
                await broadcast_to_player(session_store, partner, payload)

                await ws.send_json({
                    "type": "sent", "to": partner, "id": saved["id"],
                    "message": text, "timestamp": saved["timestamp"]
                })

                await broadcast_to_player(session_store, partner, {
                    "type": "unread", "from": player_id, "to": partner,
                    "count": unread_count_for(partner, player_id)
                })
                return

            await ws.send_json({"type": "error", "message": f"unknown type: {kind}"})
