

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..storage.json_store import TOKEN_TO_PLAYER
from ..services.presence import add_socket, remove_socket, send_to_all, get_selected, set_selected
from ..services.messages import (
    append_message, get_message_by_id, history_between,
    mark_read_pair, unread_count_for, soft_delete_message_by_id, minimal_view
)

router = APIRouter()

# def _extract_token(ws: WebSocket) -> str | None:
#     auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
#     if auth and isinstance(auth, str) and auth.lower().startswith("bearer "):
#         return auth.split(" ", 1)[1].strip()
#     return ws.query_params.get("token")

# @router.websocket("/chat")
async def chat_endpoint(ws: WebSocket, typ: str, data):

            if typ == "select":
                partner = data.get("selectedPlayer")
                set_selected(player_id, partner)
                if partner:
                    msgs = history_between(player_id, partner, viewer=player_id)
                    await ws.send_json({"type": "history", "with": partner, "messages": msgs})
                    if mark_read_pair(player_id, partner):
                        await send_to_all(player_id, {
                            "type": "unread", "from": partner, "to": player_id,
                            "count": unread_count_for(player_id, partner)
                        })
                continue

            if typ == "read":
                partner = data.get("with")
                if partner:
                    mark_read_pair(player_id, partner)
                    await send_to_all(player_id, {
                        "type": "unread", "from": partner, "to": player_id,
                        "count": unread_count_for(player_id, partner)
                    })
                continue

            if typ == "typing":
                partner = get_selected(player_id)
                if partner:
                    await send_to_all(partner, {"type": "typing", "typing": [player_id]})
                continue

            if typ == "react":
                msg_id = data.get("messageId")
                reaction = data.get("reaction")  
                if not msg_id:
                    await ws.send_json({"type": "error", "message": "missing messageId"})
                    continue

                m = get_message_by_id(msg_id)
                if not m:
                    await ws.send_json({"type": "error", "message": "message not found"})
                    continue
                if m.get("from") == player_id:
                    await ws.send_json({"type": "error", "message": "cannot react to own message"})
                    continue

                m.setdefault("reactions", {})
                if reaction in ("up", "down"):
                    m["reactions"][player_id] = reaction
                else:
                    m["reactions"].pop(player_id, None)

                await ws.send_json({"type": "react", "messageId": msg_id, "my_reaction": reaction})
                continue

            if typ == "message":
                text = data.get("message", "")
                partner = data.get("selectedPlayer") or get_selected(player_id)
                quoted_id = data.get("quotedId") or data.get("quoted_id")
                if not partner:
                    await ws.send_json({"type": "error", "message": "No partner selected"})
                    continue

                saved = append_message(player_id, partner, text, data.get("timestamp"), quoted_id=quoted_id)
                payload = minimal_view(saved) | {"type": "message", "sender": player_id, "to": partner}

                await send_to_all(player_id, payload)
                await send_to_all(partner, payload)

                await ws.send_json({
                    "type": "sent", "to": partner, "id": saved["id"],
                    "message": text, "timestamp": saved["timestamp"]
                })

                await send_to_all(partner, {
                    "type": "unread", "from": player_id, "to": partner,
                    "count": unread_count_for(partner, player_id)
                })
                continue

            # if typ == "delete":
            #     msg_id = data.get("messageId") or data.get("message_id")
            #     if not msg_id:
            #         await ws.send_json({"type": "error", "message": "missing messageId"})
            #         continue

            #     updated = soft_delete_message_by_id(msg_id, requester_id=player_id)
            #     if not updated:
            #         await ws.send_json({"type": "error", "message": "delete_not_allowed_or_not_found", "messageId": msg_id})
            #         continue

            #     payload = {
            #         "type": "message_updated",
            #         "message": {
            #             "id": updated["id"],
            #             "from": updated.get("from"),
            #             "to": updated.get("to"),
            #             "deleted": True,
            #             "text": "",
            #             "updated_at": updated.get("updated_at"),
            #         }
            #     }
            #     for pid in (updated.get("from"), updated.get("to")):
            #         if pid:
            #             await send_to_all(pid, payload)
            #     continue

            await ws.send_json({"type": "error", "message": f"unknown type: {typ}"})

    except WebSocketDisconnect:
        pass
    finally:
        remove_socket(player_id, ws)
