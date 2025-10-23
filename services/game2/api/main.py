import json
import logging
from typing import Any, get_args

from fastapi import FastAPI, WebSocket
from services.game2.core.settings import DATA_DIR
from services.game2.hub.manager import Hub
from services.game2.hub.types import Direction, IncomingMsg
from services.game2.data.db_players import find_nearest_player_in_chunk
DATA_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
app = FastAPI(title="Voxel Server")
hub = Hub()

async def _safe_send_json(ws: WebSocket, obj: Any) -> None:
    try:
        await ws.send_text(json.dumps(obj))
    except Exception as e:
        logger.warning("Failed to send WS message: %s", e)



async def _handle_move(ws: WebSocket, key) -> None:
    if key == "up":    await hub.move(ws, -1, 0)
    if key == "down":  await hub.move(ws, +1, 0)
    if key == "left":  await hub.move(ws, 0, -1)
    if key == "right": await hub.move(ws, 0, +1)


async def _handle_message(ws: WebSocket, data: IncomingMsg) -> None:
    content = data.get("content", "").strip()

    if content: 
        await hub.write_message(ws, content)
    else:      
        await _safe_send_json(ws, {"ok": False, "type": "error", "code": "EMPTY_MESSAGE", "msg": "Message content is empty"})



async def _handle_command(ws: WebSocket, data: IncomingMsg) -> None:
    command = (data.get("command") or "").lower()
    try:
        if command in get_args(Direction):  await _handle_move(ws, command)  # type: ignore[arg-type]
        elif command in ("c", "color", "color++"):      await hub.color_plus_plus(ws)
        elif command == "m":                             await _handle_message(ws, data)
        elif command == "whereami":                      await hub.whereami(ws)
    except Exception as e:
        logger.exception("Action failed for command=%s: %s", command, e)
        await _safe_send_json(ws, {"ok": False, "error": "action_failed", "msg": str(e)})
   

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    try:
        await hub.connect(ws)
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("payload must be an object")
            except Exception as e:
                await _safe_send_json(ws, {
                    "ok": False,
                    "type": "error",
                    "code": "BAD_PAYLOAD",
                    "msg": str(e),
                })
                continue
            await _handle_command(ws, data)

    except Exception as e:
        logger.exception("WS connection failed: %s", e)
        try:
            await ws.close(code=1011, reason="internal error")
        except Exception:
                logger.warning("Failed to close WebSocket cleanly: %s", e)

    finally:
        try:
            await hub.disconnect(ws)
        except Exception as e:
            logger.warning("Failed to disconnect WS cleanly: %s", e)



@app.get("/nearest-player/{player_id}")

async def nearest_player(player_id: str):
    pid = find_nearest_player_in_chunk(player_id)
    if not pid:
        return {"ok": False, "nearest" : None}
    return {"ok":True, "nearest": pid}
