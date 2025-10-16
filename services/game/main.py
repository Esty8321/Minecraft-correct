import os
import json
import logging
import traceback
from typing import Any, Optional, Tuple, TypedDict, Literal

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from .settings import W, H
from .hub import Hub
from .db import clear_player_bits_all

JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "CHANGE_ME_123456789")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

LOGGER = logging.getLogger("voxel-server")
if not LOGGER.handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

app = FastAPI(title="-Voxel Server-")
hub = Hub()

class IncomingMsg(TypedDict, total=False):
    k: str
    content: str

MoveKey = Literal["arrowup", "up", "arrowdown", "down", "arrowleft", "left", "arrowright", "right"]

@app.on_event("startup")
async def on_startup() -> None:
    LOGGER.info("Startup: clearing all player bits…")
    clear_player_bits_all()
    LOGGER.info("Startup complete.")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    LOGGER.info("Shutdown: disconnecting all websockets…")
    for ws in list(hub.pos_by_ws.keys()):
        try:
            await hub.disconnect(ws)
        except Exception as e:
            LOGGER.warning("Failed to disconnect ws during shutdown: %r", e)
    LOGGER.info("Shutdown complete.")

@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "w": W, "h": H}

def _extract_token(ws: WebSocket) -> Optional[str]:
    try:
        token = ws.query_params.get("token")
        if token:
            return token
    except Exception:
        pass
    try:
        auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            return auth[7:]
    except Exception:
        pass
    return None

def _verify_token_or_reason(token: Optional[str]) -> Tuple[bool, str]:
    if not token:
        return False, "no token provided"
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return True, ""
    except JWTError as e:
        return False, f"invalid token: {e}"
    except Exception as e:
        return False, f"token error: {e}"

async def _safe_send_json(ws: WebSocket, obj: Any) -> None:
    try:
        await ws.send_text(json.dumps(obj))
    except Exception as e:
        LOGGER.debug("send_json failed: %r", e)

async def _close_with_reason(ws: WebSocket, code: int, reason: str) -> None:
    try:
        await ws.close(code=code, reason=reason)
    except Exception:
        pass

async def _handle_move(ws: WebSocket, key: MoveKey) -> None:
    if key in ("arrowup", "up"):
        await hub.move(ws, -1, 0)
    elif key in ("arrowdown", "down"):
        await hub.move(ws, +1, 0)
    elif key in ("arrowleft", "left"):
        await hub.move(ws, 0, -1)
    elif key in ("arrowright", "right"):
        await hub.move(ws, 0, +1)
    await hub.check_for_message(ws)

async def _handle_message(ws: WebSocket, data: IncomingMsg) -> None:
    content = (data.get("content") or "").strip()
    if content:
        await hub.write_message(ws, content)
    else:
        await _safe_send_json(
            ws,
            {"ok": False, "type": "error", "code": "EMPTY_MESSAGE", "msg": "Message content is empty"},
        )

async def _handle_command(ws: WebSocket, data: IncomingMsg) -> None:
    k = (data.get("k") or "").lower()
    try:
        if k in ("arrowup", "up", "arrowdown", "down", "arrowleft", "left", "arrowright", "right"):
            await _handle_move(ws, k)  # type: ignore[arg-type]
        elif k in ("c", "color", "color++"):
            await hub.color_plus_plus(ws)
        elif k == "m":
            await _handle_message(ws, data)
        elif k in ("whereami",):
            await hub._send_chunk(ws)
        elif k:
            LOGGER.info("Unknown key received: %s", k)
    except Exception as e:
        LOGGER.exception("Action failed for key=%s: %s", k, e)
        await _safe_send_json(ws, {"ok": False, "error": "action_failed", "msg": str(e)})

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    token = _extract_token(ws)
    ok, reason = _verify_token_or_reason(token)
    if not ok:
        await _close_with_reason(ws, 1008, reason)
        return
    try:
        await ws.accept()
        await hub.connect(ws)
        LOGGER.info("Client connected: %s", ws.client)
        try:
            await hub.check_for_message(ws)
        except Exception:
            pass
    except Exception as e:
        LOGGER.exception("Failed to accept/connect client: %s", e)
        await _close_with_reason(ws, 1011, "hub.connect error")
        return
    try:
        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect as wd:
                LOGGER.info("WebSocketDisconnect: %s", wd)
                break
            except Exception as e:
                LOGGER.exception("receive_text error: %s", e)
                break
            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("payload must be an object")
            except Exception as e:
                LOGGER.debug("JSON parse error: %s raw=%r", e, raw)
                continue
            await _handle_command(ws, data)
    finally:
        LOGGER.info("Connection closing → hub.disconnect")
        try:
            await hub.disconnect(ws)
            LOGGER.info("Disconnected successfully.")
        except Exception as e:
            LOGGER.exception("Error during disconnect: %s", e)
