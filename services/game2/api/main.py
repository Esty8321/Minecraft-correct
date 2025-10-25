import json
import logging
from typing import Any, get_args
from fastapi import FastAPI, WebSocket

from ..data.db_players import PlayerDB
from ..data.db_chunks import ChunkDB
from ..data.db_history import PlayerActionHistory
from ..data.db_scrolls import ScrollDB
from ..hub.manager import Hub
from ..hub.types import Direction, IncomingMsg
from ..hub.world import WorldService
from ..hub.sessions import SessionStore
from ..hub.scrolls import ScrollService
from ..hub.movement import MovementService
from ..hub.bot import BotService
from ..hub.color import ColorService
from ..hub.ws_utils import WebSocketUtils

from ..core.settings import DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
app = FastAPI(title="Voxel Server")

player_db = PlayerDB()
chunk_db = ChunkDB()
player_actions_history = PlayerActionHistory()
scrolls_db = ScrollDB()

world_service = WorldService(chunk_db, player_db, player_actions_history)
session_store = SessionStore()
scroll_service = ScrollService(world_service, session_store, scrolls_db, chunk_db, player_actions_history)
movement_service = MovementService(world_service, chunk_db, player_db)
color_service = ColorService(world_service, scroll_service)

bot_service = BotService(world_service,movement_service,scroll_service,color_service)

hub = Hub(world_service, movement_service,
          scroll_service,bot_service,session_store, color_service)


async def _handle_move(ws: WebSocket, key) -> None:
    if key == "up":    await hub.move(ws, -1, 0)
    if key == "down":  await hub.move(ws, +1, 0)
    if key == "left":  await hub.move(ws, 0, -1)
    if key == "right": await hub.move(ws, 0, +1)


async def _handle_scroll(ws: WebSocket, data: IncomingMsg) -> None:
    content = (data.get("content") or "").strip()
    if content: 
        await hub.write_scroll(ws, content)
    else:      
        await WebSocketUtils.send_json(ws, {"ok": False, "type": "error", "code": "EMPTY_MESSAGE", "msg": "Message content is empty"})


async def _handle_command(ws: WebSocket, data: IncomingMsg) -> None:
    command = (data.get("command") or "").lower()
    print("the command is", command)
    try:
        if command in get_args(Direction):  
            await _handle_move(ws, command)  # type: ignore[arg-type]
        elif command in ("c", "color", "color++"):    
            await hub.color_plus_plus(ws)
            
        elif command == "m":  ##??to see how can I change the name m to meaningfull name    
            await _handle_scroll(ws, data)
        elif command == "whereami":
            await hub.whereami(ws)
    except Exception as e:
        logger.exception("Action failed for key=%s: %s", command, e)
        await WebSocketUtils.send_json(ws, {"ok": False, "error": "action_failed", "msg": str(e)})
   

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
               await WebSocketUtils.send_json(ws, {
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
    pid = world_service.find_nearest_player_in_chunk(player_id)
    if not pid:
        return {"ok": False, "nearest" : None}
    return {"ok":True, "nearest": pid}
