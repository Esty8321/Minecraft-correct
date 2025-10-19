import os, json, logging
from typing import Any, Optional, Tuple, TypedDict, Literal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from ..hub.hub import Hub

JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "CHANGE_ME_123456789")
JWT_ALG    = os.getenv("JWT_ALG", "HS256")

logger = logging.getLogger(__name__)
app = FastAPI(title="Voxel Server")
hub = Hub()

class IncomingMsg(TypedDict, total=False):
    k: str
    content: str

MoveKey = Literal["up", "down", "left", "right"]

def _extract_token(ws: WebSocket) -> Optional[str]:
    token = ws.query_params.get("token")
    if token: return token
    auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
    if isinstance(auth, str) and auth.lower().startswith("bearer "):
        return auth[7:]
    return None

def _verify_token_or_reason(token: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    if not token: return False, "no token provided", None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = str(payload.get("sub") or payload.get("id") or "")
        if not user_id:
            return False, "token missing sub/id", None
        return True, "", user_id
    except JWTError as e:
        return False, f"invalid token: {e}", None
    except Exception as e:
        return False, f"token error: {e}", None

async def _safe_send_json(ws: WebSocket, obj: Any) -> None:
    try:
        await ws.send_text(json.dumps(obj))
    except Exception:
        pass

async def _handle_move(ws: WebSocket, key: MoveKey) -> None:
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
        if k in ("up", "down", "left", "right"):  await _handle_move(ws, k)  # type: ignore[arg-type]
        elif k in ("c", "color", "color++"):      await hub.color_plus_plus(ws)
        elif k == "m":                             await _handle_message(ws, data)
        elif k == "whereami":                      await hub._send_chunk(ws)
    except Exception as e:
        logger.exception("Action failed for key=%s: %s", k, e)
        await _safe_send_json(ws, {"ok": False, "error": "action_failed", "msg": str(e)})

@app.get("/healthz")
def healthz(): return {"ok": True}

@app.get("/status")
def status():  return {"ok": True, "service": "voxel", "version": 1}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    token = _extract_token(ws)
    ok, reason, user_id = _verify_token_or_reason(token)
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
 