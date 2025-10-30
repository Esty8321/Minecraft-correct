import json
import logging
from typing import Any, get_args
from fastapi import FastAPI, WebSocket
from starlette.websockets    import WebSocketDisconnect
from ..core.settings import (
    CMD_UP, CMD_DOWN, CMD_LEFT, CMD_RIGHT,
    CMD_COLOR_PLUS_PLUS, CMD_SCROLL_WRITE, CMD_WHEREAMI, CHAT_TYPES, DATA_DIR
)
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
from ..data.db_chat import ChatDB
from ..chat.chat_manager import  ChatManager
from ..chat.messages import MessageService

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


chat_db = ChatDB()
message_service = MessageService(chat_db)
chat_manager = ChatManager(session_store, world_service, message_service, chunk_players)


async def _handle_move(ws: WebSocket, key) -> None:
    if key == CMD_UP:    await hub.move(ws, -1, 0)
    if key == CMD_DOWN:  await hub.move(ws, +1, 0)
    if key == CMD_LEFT:  await hub.move(ws, 0, -1)
    if key == CMD_RIGHT: await hub.move(ws, 0, +1)
   

async def _handle_scroll(ws: WebSocket, data: IncomingMsg) -> None:
    content = (data.get("content") or "").strip()
    if content: 
        await hub.write_scroll(ws, content)
    else:      
        await WebSocketUtils.send_json(ws, {"ok": False, "type": "error", "code": "EMPTY_MESSAGE", "msg": "Message content is empty"})


async def _handle_command(ws: WebSocket, data: IncomingMsg) -> None:
    command = (data.get("command") or "").lower()
    try:
        if command in get_args(Direction):  
            await _handle_move(ws, command)
        elif command == CMD_COLOR_PLUS_PLUS:  
            await hub.color_plus_plus(ws)
            
        elif command == CMD_SCROLL_WRITE:
            await _handle_scroll(ws, data)
        elif command == CMD_WHEREAMI:
            await hub.whereami(ws)
    except Exception as e:
        await WebSocketUtils.send_json(ws, {"ok": False, "error": "action_failed", "msg": str(e)})


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """Main WebSocket entrypoint handling both game and chat traffic."""
    await ws.accept()
    await hub.connect(ws)
    
    player = session_store.get(ws)
    player_id = player.state.user_id if player else None
     
    try:
        while True:
            raw = await ws.receive_text()
            try:   
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("Payload must be a JSON object")               
            except Exception as e:
                await WebSocketUtils.send_json(ws, {
                    "ok": False,
                    "type": "error",
                    "code": "BAD_PAYLOAD",
                    "msg": str(e),
                })
                continue
            if player_id is None:
                logger.log("missing id")
                
            typ = (data.get("type") or "").strip().lower() if "type" in data else ""
            if typ in CHAT_TYPES:
                if not player_id:
                     await ws.send_json({"type": "error", "message": "no player session"})
                     continue
                await chat_manager.handle_chat(ws, typ, data, player_id)
            else:
                await _handle_command(ws, data)            
    except WebSocketDisconnect:
        print("[INFO] WebSocket disconnected cleanly")
    finally:
        await hub.disconnect(ws)
        
        
@app.get("/chat/history")
async def chat_history(me: str, with_id: str):
    msgs = message_service.history_between(me, with_id, viewer= me)
    return{
        "ok":True, 
        "messages":msgs,
    }