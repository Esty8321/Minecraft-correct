from __future__ import annotations
import asyncio
import json
import logging
import random
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple, Literal, TypedDict
import torch
from fastapi import WebSocket


from .settings import BIT_HAS_LINK, W, H, DTYPE, BIT_IS_PLAYER
from .bits import set_bit, get_bit, make_color, with_player, without_player, get_player_color_by_user_id
from .ids import chunk_id_from_coords, coords_from_chunk_id
from .db import load_message, save_chunk, load_chunk, save_message
from .models import Message
from .players_db import get_player_position, save_player_position

from services.game.db_history import (
    append_player_action,
    TOKEN_RIGHT, TOKEN_LEFT, TOKEN_UP, TOKEN_DOWN, TOKEN_COLOR,
)


async def extract_user_id(ws :WebSocket)->str:
            from jose import jwt
            from .main import JWT_ALG, JWT_SECRET
            token = ws.query_params.get("token")
            user_id = None
            if token:
                try:
                    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
                    user_id = payload.get("sub") or payload.get("id")
                    ##bring here the color of the player according his id??
                except Exception:
                    LOGGER.error("failed to find id by the token")
            return user_id

LOGGER = logging.getLogger("voxel-hub")
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

Direction = Literal["up", "down", "left", "right"]##use only with this directions??

@dataclass(frozen=True)
class Coord:
    row: int
    col: int

@dataclass
class PlayerState:
    chunk_id: str
    pos: Coord
    visible_cell: torch.Tensor
    underlying_cell: torch.Tensor
    color: torch.Tensor

class MatrixPayload(TypedDict):
    type: Literal["matrix"]
    w: int
    h: int
    data: list[int]
    chunk_id: str
    total_players: int

class Hub:
    def __init__(self) -> None:
        self._chunks: Dict[str, torch.Tensor] = {}
        self._chunk_watchers: Dict[str, Set[WebSocket]] = {}
        self._root_chunk_id = chunk_id_from_coords(0, 0)
        self._ensure_chunk(self._root_chunk_id)
        self._sockets: Set[WebSocket] = set()
        self._state_by_ws: Dict[WebSocket, PlayerState] = {}
        self._last_msg_pos_by_ws: Dict[WebSocket, Optional[Tuple[str, int, int]]] = {}
        self._lock = asyncio.Lock()
        self._user_id_by_ws: Dict[WebSocket, str] = {}

    # ---------- ליבה: ניהול לוחות ----------

    def _ensure_chunk(self, chunk_id: str) -> torch.Tensor:
        if chunk_id in self._chunks:
            return self._chunks[chunk_id]
        board = load_chunk(chunk_id)
        if board is None:
            board = torch.zeros((H, W), dtype=DTYPE)
            save_chunk(chunk_id, board)
        self._chunks[chunk_id] = board
        return board

    @staticmethod
    def _is_empty_cell(board: torch.Tensor, r: int, c: int) -> bool:
        return int(get_bit(board[r, c], BIT_IS_PLAYER)) == 0

    def _random_empty_cell(self, board: torch.Tensor) -> Coord:
        for _ in range(4096):
            r = random.randrange(H)
            c = random.randrange(W)
            if self._is_empty_cell(board, r, c):
                return Coord(r, c)
        return Coord(H // 2, W // 2)

    @staticmethod
    def _neighbor_chunk_id(chunk_id: str, direction: Direction) -> str:
        cx, cy = coords_from_chunk_id(chunk_id)
        if direction == "up":
            cy -= 1
        elif direction == "down":
            cy += 1
        elif direction == "left":
            cx -= 1
        else:
            cx += 1
        return chunk_id_from_coords(cx, cy)
    
    async def reject_connection(self, ws: WebSocket, reason: str = "Unauthorized")->None:
        try:
            await ws.close(code = 4001, reason=reason)
        except Exception:
            LOGGER.error(str)
        self._sockets.discard(ws)

    # ---------- חיבור/ניתוק ----------

    async def connect(self, ws: WebSocket) -> None:
        self._sockets.add(ws)
        user_id = await extract_user_id(ws)
        if user_id is None:
            await self.reject_connection(ws,"Unauthorized: invalid or missing token")
            return 
        chunk_id, spawn = await self._get_spawn_position(user_id)
        color = get_player_color_by_user_id(user_id) ##change it to take the color from the function of Adina in the bit file
        await self._spawn_player(ws, user_id, chunk_id, spawn, color)
        await self._broadcast_chunk(chunk_id)
        LOGGER.info(f"Player {user_id} connected at {chunk_id}:{spawn.row},{spawn.col}")


    async def _get_spawn_position(self, user_id:str)->tuple[str, Coord]:
        pos = get_player_position(user_id)
        if pos:
            chunk_id, row, col = pos
            board = self._ensure_chunk(chunk_id)
            spawn = Coord(row, col) if self._is_empty_cell(board, row, col) else self._random_empty_cell(board)#mabye can I erase the random becuase it can't be that someone will take the place of the user after he connected at his first time to the game
        else:
            chunk_id = self._root_chunk_id
            board = self._ensure_chunk(chunk_id)
            spawn = self._random_empty_cell(board)
        return chunk_id, spawn
    
    async def _spawn_player(self, ws: WebSocket, user_id: str, chunk_id: str, spawn: Coord, color: torch.Tensor) -> PlayerState:
        """Create and register the player on the board and in memory."""
        async with self._lock:
            board = self._ensure_chunk(chunk_id)
            underlying = without_player(board[spawn.row, spawn.col])
            visible = with_player(color)
            board[spawn.row, spawn.col] = visible
            save_chunk(chunk_id, board)

            state = PlayerState(chunk_id, spawn, visible.clone(), underlying, color)
            self._state_by_ws[ws] = state
            if not hasattr(self, "_user_id_by_ws"):
                self._user_id_by_ws = {}
            self._user_id_by_ws[ws] = user_id  

            save_player_position(user_id, chunk_id, spawn.row, spawn.col)
            self._chunk_watchers.setdefault(chunk_id, set()).add(ws)

        return state
            
    
    def _assign_color(self, user_id: str) -> torch.Tensor:##??delete this funcion after and use at the update funcion by the user_id
        """Assign player color (could later depend on user_id)."""
        pr, pg, pb = (random.randint(0, 3) for _ in range(3))
        return make_color(pr, pg, pb) 


    async def disconnect(self, ws: WebSocket) -> None:
        prev_chunk_id: Optional[str] = None
        state_snapshot: Optional[PlayerState] = None
        async with self._lock:
            state = self._state_by_ws.pop(ws, None)
            if state:
                state_snapshot = PlayerState(
                    chunk_id=state.chunk_id,
                    pos=Coord(state.pos.row, state.pos.col),
                    visible_cell=state.visible_cell.clone(),
                    underlying_cell=state.underlying_cell.clone(),
                    color=state.color.clone(),
                )
                board = self._ensure_chunk(state.chunk_id)
                board[state.pos.row, state.pos.col] = state.underlying_cell##??becuase the bot continue , need to return at the board and only act the funcion without_player from the board[state.spawn[col, row]]

                save_chunk(state.chunk_id, board)##??
                watchers = self._chunk_watchers.get(state.chunk_id, set())
                watchers.discard(ws)
                prev_chunk_id = state.chunk_id

            self._last_msg_pos_by_ws.pop(ws, None)
            self._sockets.discard(ws)
       
        if hasattr(self, "_user_id_by_ws"):
            user_id = self._user_id_by_ws.get(ws)
            state = self._state_by_ws.get(ws)
        if user_id and state:
            save_player_position(user_id, state.chunk_id, state.pos.row, state.pos.col)
        
        if hasattr(self, "_user_id_by_ws") and ws in self._user_id_by_ws:
            del self._user_id_by_ws[ws]
            

    def _direction_token(self, dr: int, dc: int) -> int:
        if dr == 0 and dc == 1:
            return TOKEN_RIGHT
        if dr == 0 and dc == -1:
            return TOKEN_LEFT
        if dr == -1 and dc == 0:
            return TOKEN_UP
        return TOKEN_DOWN

    @staticmethod
    def _in_bounds(r: int, c: int) -> bool:
        return 0 <= r < H and 0 <= c < W

    def _compose_entry_cells(
        self, board: torch.Tensor, r: int, c: int, color: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        מחזיר (new_underlying, new_visible) עבור כניסה לתא יעד, כולל שימור דגל לינק אם היה.
        """
        dest_before = board[r, c]
        new_underlying = without_player(dest_before)
        new_visible = with_player(color)
        if get_bit(dest_before, BIT_HAS_LINK):
            new_visible = set_bit(new_visible, BIT_HAS_LINK, True)
        return new_underlying, new_visible

    def _apply_move_within_chunk(
        self, state: PlayerState, board: torch.Tensor, nr: int, nc: int
    ) -> bool:
        """מזיז שחקן בתוך צ'אנק אם היעד פנוי. מחזיר True אם זז בפועל."""
        if not self._is_empty_cell(board, nr, nc):
            return False

        # שחרור התא הנוכחי
        board[state.pos.row, state.pos.col] = state.underlying_cell

        # הכנת תאי יעד
        new_underlying, new_visible = self._compose_entry_cells(board, nr, nc, state.color)

        # כתיבה ליעד ועדכון סטייט
        board[nr, nc] = new_visible
        save_chunk(state.chunk_id, board)

        state.pos = Coord(nr, nc)
        state.underlying_cell = new_underlying
        state.visible_cell = new_visible
        return True

    @staticmethod
    def _edge_direction(nr: int, nc: int) -> Direction:
        if nr < 0:
            return "up"
        if nr >= H:
            return "down"
        if nc < 0:
            return "left"
        return "right"

    @staticmethod
    def _edge_target_for_direction(state: PlayerState, direction: Direction) -> Coord:
        if direction == "up":
            return Coord(H - 1, state.pos.col)
        if direction == "down":
            return Coord(0, state.pos.col)
        if direction == "left":
            return Coord(state.pos.row, W - 1)
        return Coord(state.pos.row, 0)

    def _transfer_between_chunks(self, ws: WebSocket, state: PlayerState, direction: Direction) -> tuple[bool, str]:
        """
        מעביר שחקן לצ'אנק שכן בהתאם לכיוון. מחזיר (moved, old_chunk_id).
        מטפל בעדכון לוחות, צופים ושמירה לדיסק.
        """
        old_chunk_id = state.chunk_id
        old_board = self._ensure_chunk(old_chunk_id)

        new_chunk_id = self._neighbor_chunk_id(old_chunk_id, direction)
        new_board = self._ensure_chunk(new_chunk_id)
        target = self._edge_target_for_direction(state, direction)

        if not self._is_empty_cell(new_board, target.row, target.col):
            return False, old_chunk_id

        # שחרור מהתא הישן ושמירה
        old_board[state.pos.row, state.pos.col] = state.underlying_cell
        save_chunk(old_chunk_id, old_board)

        # כניסה לתא חדש
        new_underlying, new_visible = self._compose_entry_cells(new_board, target.row, target.col, state.color)
        new_board[target.row, target.col] = new_visible
        save_chunk(new_chunk_id, new_board)

        # עדכון קבוצות צופים
        self._chunk_watchers.setdefault(new_chunk_id, set()).add(ws)
        self._chunk_watchers.get(old_chunk_id, set()).discard(ws)

        # עדכון סטייט
        state.chunk_id = new_chunk_id
        state.pos = target
        state.underlying_cell = new_underlying
        state.visible_cell = new_visible

        return True, old_chunk_id

    def _save_player_pos_if_known(self, ws: WebSocket, state: PlayerState) -> None:
        user_id = self._user_id_by_ws.get(ws)
        if user_id:
            save_player_position(user_id, state.chunk_id, state.pos.row, state.pos.col)

    async def _post_move_housekeeping(self, ws: WebSocket, state: PlayerState, old_chunk_id: Optional[str] = None) -> None:
        """שידור/הודעות אחרי תנועה."""
        if old_chunk_id and old_chunk_id != state.chunk_id:
            await self._broadcast_chunk(old_chunk_id)
            await self._broadcast_chunk(state.chunk_id)
        else:
            await self._broadcast_chunk(state.chunk_id)
        await self._maybe_send_message_at(ws)


    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        tok = self._direction_token(dr, dc)

        async with self._lock:
            #do the funcion that now to do the command of the move ??
            state = self._state_by_ws[ws]
            board = self._ensure_chunk(state.chunk_id)


            nr, nc = state.pos.row + dr, state.pos.col + dc
            moved = False
            old_chunk_id: Optional[str] = None

            if self._in_bounds(nr, nc):
                moved = self._apply_move_within_chunk(state, board, nr, nc)
                if moved:
                    append_player_action(self._player_id(ws), state.chunk_id, tok)

                    self._save_player_pos_if_known(ws, state)
            else:
                direction = self._edge_direction(nr, nc)
                moved, old_chunk_id = self._transfer_between_chunks(ws, state, direction)
                if moved:
                    append_player_action(self._player_id(ws), state.chunk_id, tok)
                    self._save_player_pos_if_known(ws, state)

        if moved:
            await self._post_move_housekeeping(ws, state, old_chunk_id=old_chunk_id)



    async def color_plus_plus(self, ws: WebSocket) -> None:
        async with self._lock:
            state = self._state_by_ws[ws]
            board = self._ensure_chunk(state.chunk_id)
            pr, pg, pb = (random.randint(0, 3) for _ in range(3))
            new_color = make_color(pr, pg, pb)
            state.color = new_color
            state.underlying_cell = new_color
            board[state.pos.row, state.pos.col] = with_player(new_color)
            save_chunk(state.chunk_id, board)

            append_player_action(self._player_id(ws), state.chunk_id, TOKEN_COLOR)

        await self._broadcast_chunk(state.chunk_id)

    async def _send_chunk(self, ws: WebSocket) -> None:
        state = self._state_by_ws.get(ws)
        if not state:
            return    
        board = self._ensure_chunk(state.chunk_id)
        payload: MatrixPayload = {
            "type": "matrix",
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": state.chunk_id,
            "total_players": len(self._sockets),
        }
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as e:
            LOGGER.debug("send chunk failed: %r", e)

    async def _broadcast_chunk(self, chunk_id: str) -> None:
        board = self._ensure_chunk(chunk_id)
        payload: MatrixPayload = {
            "type": "matrix",
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": chunk_id,
            "total_players": len(self._sockets),
        }
        dead: Set[WebSocket] = set()
        for s in list(self._chunk_watchers.get(chunk_id, set())):
            try:
                await s.send_text(json.dumps(payload))
            except Exception as e:
                LOGGER.debug("broadcast failed: %r", e)
                dead.add(s)
        for s in dead:
            try:
                await self.disconnect(s)
            except Exception as e:
                LOGGER.debug("disconnect failed: %r", e)

    async def _maybe_send_message_at(self, ws: WebSocket) -> None:
        state = self._state_by_ws.get(ws)
        if not state:
            return
        board = self._ensure_chunk(state.chunk_id)
        cell_under = state.underlying_cell or without_player(board[state.pos.row, state.pos.col])
        if get_bit(cell_under, BIT_HAS_LINK):
            last = self._last_msg_pos_by_ws.get(ws)
            current_pos = (state.chunk_id, state.pos.row, state.pos.col)
            if last == current_pos:
                return
            message = load_message(state.chunk_id, state.pos.row, state.pos.col)
            if message:
                try:
                    await ws.send_text(json.dumps({"type": "message", "data": message}))
                except Exception as e:
                    LOGGER.debug("send message failed: %r", e)
                self._last_msg_pos_by_ws[ws] = current_pos
        else:
            self._last_msg_pos_by_ws[ws] = None

    async def check_for_message(self, ws: WebSocket) -> None:
        await self._maybe_send_message_at(ws)

    async def write_message(self, ws: WebSocket, content: str) -> None:
        async with self._lock:
            try:
                state = self._state_by_ws[ws]
                board = self._ensure_chunk(state.chunk_id)
                existing = load_message(state.chunk_id, state.pos.row, state.pos.col)
                if existing or get_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK):
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "code": "SPACE_OCCUPIED",
                        "message": "This spot already has a message!"
                    }))
                    return
                message = Message(
                    content=content,
                    author=str(id(ws)),
                    chunk_id=state.chunk_id,
                    position=(state.pos.row, state.pos.col)
                )
                save_message(message)
                board[state.pos.row, state.pos.col] = set_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK, True)
                state.underlying_cell = set_bit(state.underlying_cell, BIT_HAS_LINK, True)
                save_chunk(state.chunk_id, board)
            except Exception as e:
                LOGGER.error("Failed to write message: %r", e)
                try:
                    await ws.send_text(json.dumps({"type": "error", "message": "Failed to save message"}))
                except Exception:
                    pass
                return

        # שידור והכרזה אחרי שחרור הנעילה
        await self._broadcast_chunk(state.chunk_id)
        notice = json.dumps({"type": "announcement", "data": {"text": "A player hid a treasure"}})
        for target_ws in list(self._chunk_watchers.get(state.chunk_id, set())):
            try:
                await target_ws.send_text(notice)
            except Exception as e:
                LOGGER.debug("send announcement failed: %r", e)

    def _player_id(self, ws: WebSocket) -> str:
        if hasattr(self, "_user_id_by_ws"):
            user_id = self._user_id_by_ws.get(ws)
            print("user_id", user_id)
            if user_id is not None:
                return user_id

