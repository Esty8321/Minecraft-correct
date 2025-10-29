import json
import logging
from typing import Any, get_args
from fastapi import FastAPI, WebSocket
from starlette.websockets    import WebSocketDisconnect

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
from ..hub.chunk_players import ChunkPlayers
from ..core.settings import DATA_DIR

from ..chat.chat_manager import chat_endpoint
DATA_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
app = FastAPI(title="NanoVerse")

player_db = PlayerDB()
chunk_db = ChunkDB()
player_actions_history = PlayerActionHistory()
scrolls_db = ScrollDB()
chunk_players = ChunkPlayers()


world_service = WorldService(chunk_db, player_db, player_actions_history, chunk_players)
session_store = SessionStore()
scroll_service = ScrollService(world_service, session_store, scrolls_db, chunk_db, player_actions_history, player_db)

movement_service = MovementService(world_service, chunk_db, player_db, chunk_players)
color_service = ColorService(world_service, scroll_service)
bot_service = BotService(world_service,movement_service,scroll_service,color_service)

hub = Hub(world_service, movement_service,
          scroll_service,bot_service,session_store, color_service, player_db, chunk_players)


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
    """Main WebSocket entrypoint handling both game and chat traffic."""
    await ws.accept()
    print("New WebSocket connection")
    await hub.connect(ws)

    try:
        while True:
            try:
                raw = await ws.receive_text()
                data = json.loads(raw)

                if not isinstance(data, dict):
                    raise ValueError("Payload must be a JSON object")

                typ = (data.get("type") or "").strip().lower()
   
                if typ:
                    print("I got a chat message")
                    # Route chat messages
                    player = session_store.get(ws)
                    if not player:
                        raise ValueError("No active player session for this connection")

                    player_id = player.state.user_id
                    await chat_endpoint(ws, data, player_id)
                else:
                    # Route game commands
                    await _handle_command(ws, data)

            except json.JSONDecodeError:
                await WebSocketUtils.send_json(ws, {
                    "ok": False,
                    "type": "error",
                    "code": "BAD_JSON",
                    "msg": "Invalid JSON payload",
                })
            except Exception as e:
                await WebSocketUtils.send_json(ws, {
                    "ok": False,
                    "type": "error",
                    "code": "BAD_PAYLOAD",
                    "msg": str(e),
                })

    except WebSocketDisconnect:
        print("[INFO] WebSocket disconnected cleanly")
    finally:
        await hub.disconnect(ws)

         

