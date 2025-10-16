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
from .bits import set_bit, get_bit, make_color, with_player, without_player
from .ids import chunk_id_from_coords, coords_from_chunk_id
from .db import load_message, save_chunk, load_chunk, save_message
from .models import Message

from services.game.db_history import (
    append_player_action,
    TOKEN_RIGHT, TOKEN_LEFT, TOKEN_UP, TOKEN_DOWN, TOKEN_COLOR,
)


LOGGER = logging.getLogger("voxel-hub")
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

Direction = Literal["up", "down", "left", "right"]

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

    async def connect(self, ws: WebSocket) -> None:
        self._sockets.add(ws)
        async with self._lock:
            chunk_id = self._root_chunk_id
            board = self._ensure_chunk(chunk_id)
            spawn = self._random_empty_cell(board)
            pr, pg, pb = (random.randint(0, 3) for _ in range(3))
            color = make_color(pr, pg, pb)
            underlying = without_player(board[spawn.row, spawn.col])
            visible = with_player(color)
            board[spawn.row, spawn.col] = visible
            save_chunk(chunk_id, board)
            self._state_by_ws[ws] = PlayerState(chunk_id, spawn, visible.clone(), underlying, color)
            self._chunk_watchers.setdefault(chunk_id, set()).add(ws)
        await self._broadcast_chunk(chunk_id)

    async def disconnect(self, ws: WebSocket) -> None:
        prev_chunk_id: Optional[str] = None
        async with self._lock:
            state = self._state_by_ws.pop(ws, None)
            if state:
                board = self._ensure_chunk(state.chunk_id)
                board[state.pos.row, state.pos.col] = state.underlying_cell
                save_chunk(state.chunk_id, board)
                watchers = self._chunk_watchers.get(state.chunk_id, set())
                watchers.discard(ws)
                prev_chunk_id = state.chunk_id
            self._last_msg_pos_by_ws.pop(ws, None)
            self._sockets.discard(ws)
        if prev_chunk_id:
            await self._broadcast_chunk(prev_chunk_id)

    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        async with self._lock:
            state = self._state_by_ws[ws]
            board = self._ensure_chunk(state.chunk_id)

            if dr == 0 and dc == 1:
                tok = TOKEN_RIGHT
            elif dr == 0 and dc == -1:
                tok = TOKEN_LEFT
            elif dr == -1 and dc == 0:
                tok = TOKEN_UP
            else:
                tok = TOKEN_DOWN

            nr, nc = state.pos.row + dr, state.pos.col + dc

            if 0 <= nr < H and 0 <= nc < W:
                if self._is_empty_cell(board, nr, nc):
                    board[state.pos.row, state.pos.col] = state.underlying_cell
                    dest_before = board[nr, nc]
                    new_underlying = without_player(dest_before)
                    new_visible = with_player(state.color)
                    if get_bit(dest_before, BIT_HAS_LINK):
                        new_visible = set_bit(new_visible, BIT_HAS_LINK, True)
                    board[nr, nc] = new_visible
                    save_chunk(state.chunk_id, board)

                    state.pos = Coord(nr, nc)
                    state.underlying_cell = new_underlying
                    state.visible_cell = new_visible

                    append_player_action(self._player_id(ws), state.chunk_id, tok)

                    await self._broadcast_chunk(state.chunk_id)
                    await self._maybe_send_message_at(ws)
                return

            if nr < 0:
                direction: Direction = "up"
            elif nr >= H:
                direction = "down"
            elif nc < 0:
                direction = "left"
            else:
                direction = "right"

            new_chunk_id = self._neighbor_chunk_id(state.chunk_id, direction)
            new_board = self._ensure_chunk(new_chunk_id)

            if direction == "up":
                target = Coord(H - 1, state.pos.col)
            elif direction == "down":
                target = Coord(0, state.pos.col)
            elif direction == "left":
                target = Coord(state.pos.row, W - 1)
            else:
                target = Coord(state.pos.row, 0)

            if self._is_empty_cell(new_board, target.row, target.col):
                board[state.pos.row, state.pos.col] = state.underlying_cell
                save_chunk(state.chunk_id, board)

                dest_before = new_board[target.row, target.col]
                new_underlying = without_player(dest_before)
                new_visible = with_player(state.color)
                if get_bit(dest_before, BIT_HAS_LINK):
                    new_visible = set_bit(new_visible, BIT_HAS_LINK, True)
                new_board[target.row, target.col] = new_visible
                save_chunk(new_chunk_id, new_board)

                self._chunk_watchers.setdefault(new_chunk_id, set()).add(ws)
                self._chunk_watchers.get(state.chunk_id, set()).discard(ws)

                old_chunk = state.chunk_id
                state.chunk_id = new_chunk_id
                state.pos = target
                state.underlying_cell = new_underlying
                state.visible_cell = new_visible

                append_player_action(self._player_id(ws), state.chunk_id, tok)

                await self._broadcast_chunk(old_chunk)
                await self._broadcast_chunk(new_chunk_id)
                await self._maybe_send_message_at(ws)

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
        await self._broadcast_chunk(state.chunk_id)
        notice = json.dumps({"type": "announcement", "data": {"text": "A player hid a treasure"}})
        for target_ws in list(self._chunk_watchers.get(state.chunk_id, set())):
            try:
                await target_ws.send_text(notice)
            except Exception as e:
                LOGGER.debug("send announcement failed: %r", e)

    def _player_id(self, ws: WebSocket) -> str:
        return f"ws-{id(ws)}"




