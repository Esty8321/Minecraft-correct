import  json, logging
from typing import Any, get_args
from fastapi import FastAPI, WebSocket
from jose import jwt, JWTError
from ..hub.hub import Hub
from ..hub.types import Direction , IncomingMsg
from ..hub.helper import extract_token, verify_token_or_reason


logger = logging.getLogger(__name__)
app = FastAPI(title="Voxel Server")
hub = Hub()

async def _safe_send_json(ws: WebSocket, obj: Any) -> None:
    try:
        await ws.send_text(json.dumps(obj))
    except Exception:
        pass

async def _handle_move(ws: WebSocket, key) -> None:
    if key == "up":    await hub.move(ws, -1, 0)
    if key == "down":  await hub.move(ws, +1, 0)
    if key == "left":  await hub.move(ws, 0, -1)
    if key == "right": await hub.move(ws, 0, +1)

async def _handle_message(ws: WebSocket, data: IncomingMsg) -> None:
    content = (data.get("content") or "").strip()
    if content: await hub.write_message(ws, content)
    else:       await _safe_send_json(ws, {"ok": False, "type": "error", "code": "EMPTY_MESSAGE", "msg": "Message content is empty"})

async def _handle_command(ws: WebSocket, data: IncomingMsg) -> None:
    k = (data.get("k") or "").lower()
    try:
        if k in get_args(Direction):  await _handle_move(ws, k)  # type: ignore[arg-type]
        elif k in ("c", "color", "color++"):      await hub.color_plus_plus(ws)
        elif k == "m":                             await _handle_message(ws, data)
        elif k == "whereami":                      await hub._send_chunk(ws)
    except Exception as e:
        logger.exception("Action failed for key=%s: %s", k, e)
        await _safe_send_json(ws, {"ok": False, "error": "action_failed", "msg": str(e)})


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:  
    token = extract_token(ws)
    ok, reason, user_id = verify_token_or_reason(token)
    if not ok:
        await ws.close(code=1008, reason=reason);  return  
    try:
        await ws.accept()
        await hub.connect(ws, user_id=user_id or "unknown")
    except Exception as e:   
        logger.exception("accept/connect failed: %s", e)
        await ws.close(code=1011, reason="hub.connect error"); return
    try:
        async for raw in ws.iter_text():
            try:
                data = json.loads(raw)
                if not isinstance(data, dict): raise ValueError("payload must be an object")
            except Exception:
                continue
            await _handle_command(ws, data)
    finally:
        try:
            await hub.disconnect(ws)
        except Exception:
            pass
 