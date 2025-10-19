"""
hub.py
--------

Central manager for the multiplayer game world.

Responsibilities:
- Manage player connections and positions across chunks.
- Track, save, and broadcast board (matrix) state.
- Handle movement, color updates, and hidden messages.
- Ensure concurrency safety via asyncio locks.

All functions are designed for clarity, maintainability, and production readiness.
"""

from __future__ import annotations
import asyncio
import json
import logging
import random
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple, Literal, TypedDict

import torch
from fastapi import WebSocket

# --- Core + Data imports ---
from ..core.settings import W, H, DTYPE, BIT_HAS_LINK
from ..core.bits import (
    set_bit, get_bit, make_color,
    with_player, without_player,
    get_player_color_by_user_id,
)
from ..core.ids import chunk_id_from_coords, coords_from_chunk_id
from ..data.db_messages import load_message, save_message
from ..data.db_chunks import save_chunk, load_chunk
from ..data.db_players import get_player_position, save_player_position
from ..data.db_history import append_player_action, ActionToken
from ..models.message import Message

logger = logging.getLogger(__name__)

Direction = Literal["up", "down", "left", "right"]

# ------------------------------------------------------------------------
# Data Models
# ------------------------------------------------------------------------

@dataclass(frozen=True)
class Coord:
    """A coordinate (row, col) on a board."""
    row: int
    col: int


@dataclass
class PlayerState:
    """Holds all runtime state for a connected player."""
    chunk_id: str
    pos: Coord
    visible_cell: torch.Tensor
    underlying_cell: torch.Tensor
    color: torch.Tensor


class MatrixPayload(TypedDict):
    """Payload for sending board matrix updates to clients."""
    type: Literal["matrix"]
    w: int
    h: int
    data: list[int]
    chunk_id: str
    total_players: int


MOVE_TOKENS: Dict[Tuple[int, int], ActionToken] = {
    (0, 1): ActionToken.RIGHT,
    (0, -1): ActionToken.LEFT,
    (-1, 0): ActionToken.UP,
    (1, 0): ActionToken.DOWN,
}

# ------------------------------------------------------------------------
# Hub Class
# ------------------------------------------------------------------------

class Hub:
    """
    Central controller of the multiplayer world.

    Responsibilities:
    - Manage connections and disconnections.
    - Maintain chunk data and broadcast updates.
    - Track player positions and colors.
    - Handle inter-chunk transitions and hidden messages.
    """

    def __init__(self) -> None:
        # --- world state ---
        self._chunks: Dict[str, torch.Tensor] = {}
        self._chunk_watchers: Dict[str, Set[WebSocket]] = {}
        self._root_chunk_id: str = chunk_id_from_coords(0, 0)
        self._ensure_chunk(self._root_chunk_id)

        # --- player state ---
        self._sockets: Set[WebSocket] = set()
        self._state_by_ws: Dict[WebSocket, PlayerState] = {}
        self._last_msg_pos_by_ws: Dict[WebSocket, Optional[Tuple[str, int, int]]] = {}
        self._user_id_by_ws: Dict[WebSocket, str] = {}

        # --- thread safety ---
        self._lock: asyncio.Lock = asyncio.Lock()

    # --------------------------------------------------------------------
    # Chunk management
    # --------------------------------------------------------------------

    def _ensure_chunk(self, chunk_id: str) -> torch.Tensor:
        """Ensure a chunk exists both in memory and storage."""
        if chunk_id in self._chunks:
            return self._chunks[chunk_id]
        board = load_chunk(chunk_id)
        if board is None:
            board = torch.zeros((H, W), dtype=DTYPE)
            save_chunk(chunk_id, board)
        self._chunks[chunk_id] = board
        return board

    @staticmethod
    def _is_empty(board: torch.Tensor, r: int, c: int) -> bool:
        """Return True if cell (r,c) is not occupied by a player."""
        from ..core.settings import BIT_IS_PLAYER
        return int(get_bit(board[r, c], BIT_IS_PLAYER)) == 0

    def _random_empty_cell(self, board: torch.Tensor) -> Coord:
        """Pick a random empty cell for spawning a new player."""
        for _ in range(4096):
            r, c = random.randrange(H), random.randrange(W)
            if self._is_empty(board, r, c):
                return Coord(r, c)
        return Coord(H // 2, W // 2)

    @staticmethod
    def _neighbor_chunk_id(chunk_id: str, direction: Direction) -> str:
        """Return ID of neighbor chunk in the given direction."""
        cx, cy = coords_from_chunk_id(chunk_id)
        if direction == "up": cy -= 1
        elif direction == "down": cy += 1
        elif direction == "left": cx -= 1
        elif direction == "right": cx += 1
        return chunk_id_from_coords(cx, cy)

    # --------------------------------------------------------------------
    # Connection lifecycle
    # --------------------------------------------------------------------

    async def connect(self, ws: WebSocket, user_id: str) -> None:
        """
        Handle a new player connection:
          - Find spawn position
          - Create player state
          - Broadcast updated chunk
        """
        self._sockets.add(ws)
        chunk_id, spawn = await self._get_spawn_position(user_id)
        color = get_player_color_by_user_id(user_id)
        await self._spawn_player(ws, user_id, chunk_id, spawn, color)
        await self._broadcast_chunk(chunk_id)
        logger.info(f"Player {user_id} connected at {chunk_id}:{spawn.row},{spawn.col}")

    async def disconnect(self, ws: WebSocket) -> None:
        """Clean up and persist state on disconnect."""
        async with self._lock:
            state = self._state_by_ws.pop(ws, None)
            user_id = self._user_id_by_ws.pop(ws, None)
            self._last_msg_pos_by_ws.pop(ws, None)
            self._sockets.discard(ws)

            if state:
                board = self._ensure_chunk(state.chunk_id)
                board[state.pos.row, state.pos.col] = state.underlying_cell
                save_chunk(state.chunk_id, board)
                self._chunk_watchers.get(state.chunk_id, set()).discard(ws)
                if user_id:
                    save_player_position(user_id, state.chunk_id, state.pos.row, state.pos.col)
                    logger.info(f"Player {user_id} disconnected from {state.chunk_id}")

    async def _get_spawn_position(self, user_id: str) -> Tuple[str, Coord]:
        """Return last known or new spawn position."""
        pos = get_player_position(user_id)
        if pos:
            chunk_id, row, col = pos
            board = self._ensure_chunk(chunk_id)
            if self._is_empty(board, row, col):
                return chunk_id, Coord(row, col)
        board = self._ensure_chunk(self._root_chunk_id)
        return self._root_chunk_id, self._random_empty_cell(board)

    async def _spawn_player(self, ws: WebSocket, user_id: str,
                            chunk_id: str, spawn: Coord, color: torch.Tensor) -> PlayerState:
        """Insert a new player into a chunk."""
        async with self._lock:
            board = self._ensure_chunk(chunk_id)
            underlying = without_player(board[spawn.row, spawn.col])
            visible = with_player(color)
            board[spawn.row, spawn.col] = visible
            save_chunk(chunk_id, board)

            state = PlayerState(chunk_id, spawn, visible.clone(), underlying, color)
            self._state_by_ws[ws] = state
            self._user_id_by_ws[ws] = user_id
            save_player_position(user_id, chunk_id, spawn.row, spawn.col)
            self._chunk_watchers.setdefault(chunk_id, set()).add(ws)
        return state

    # --------------------------------------------------------------------
    # Movement
    # --------------------------------------------------------------------

    @staticmethod
    def _in_bounds(r: int, c: int) -> bool:
        return 0 <= r < H and 0 <= c < W

    @staticmethod
    def _edge_direction(nr: int, nc: int) -> Direction:
        """Determine which edge the player is crossing."""
        if nr < 0: return "up"
        if nr >= H: return "down"
        if nc < 0: return "left"
        return "right"

    @staticmethod
    def _edge_target_for_direction(state: PlayerState, direction: Direction) -> Coord:
        """Compute landing coordinate when crossing chunk border."""
        if direction == "up": return Coord(H - 1, state.pos.col)
        if direction == "down": return Coord(0, state.pos.col)
        if direction == "left": return Coord(state.pos.row, W - 1)
        return Coord(state.pos.row, 0)

    def _compose_entry_cells(self, board: torch.Tensor, r: int, c: int,
                             color: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Build new visible & underlying cell tensors when entering a cell."""
        dest = board[r, c]
        new_under = without_player(dest)
        new_vis = with_player(color)
        if get_bit(dest, BIT_HAS_LINK):
            new_vis = set_bit(new_vis, BIT_HAS_LINK, True)
        return new_under, new_vis

    def _apply_move_within_chunk(self, state: PlayerState, board: torch.Tensor,
                                 nr: int, nc: int) -> bool:
        """Try to move player inside same chunk."""
        if not self._is_empty(board, nr, nc):
            return False
        board[state.pos.row, state.pos.col] = state.underlying_cell
        new_under, new_vis = self._compose_entry_cells(board, nr, nc, state.color)
        board[nr, nc] = new_vis
        save_chunk(state.chunk_id, board)
        state.pos = Coord(nr, nc)
        state.underlying_cell = new_under
        state.visible_cell = new_vis
        return True
    
    async def _send_chunk(self, ws: WebSocket) -> None:
        """Send the current chunk to a single player (used for 'whereami' command)."""
        state = self._state_by_ws.get(ws)
        if not state:
            await ws.send_text(json.dumps({
                "type": "error",
                "message": "No state found for this connection."
            }))
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
            logger.debug(f"Failed to send whereami chunk: {e}")


    def _transfer_between_chunks(self, ws: WebSocket, state: PlayerState,
                                 direction: Direction) -> Tuple[bool, str]:
        """Move player across chunks."""
        old_chunk_id = state.chunk_id
        old_board = self._ensure_chunk(old_chunk_id)
        new_chunk_id = self._neighbor_chunk_id(old_chunk_id, direction)
        new_board = self._ensure_chunk(new_chunk_id)
        target = self._edge_target_for_direction(state, direction)

        if not self._is_empty(new_board, target.row, target.col):
            return False, old_chunk_id

        # leave old chunk
        old_board[state.pos.row, state.pos.col] = state.underlying_cell
        save_chunk(old_chunk_id, old_board)

        # enter new chunk
        new_under, new_vis = self._compose_entry_cells(new_board, target.row, target.col, state.color)
        new_board[target.row, target.col] = new_vis
        save_chunk(new_chunk_id, new_board)

        self._chunk_watchers.setdefault(new_chunk_id, set()).add(ws)
        self._chunk_watchers.get(old_chunk_id, set()).discard(ws)
        state.chunk_id = new_chunk_id
        state.pos = target
        state.underlying_cell = new_under
        state.visible_cell = new_vis
        return True, old_chunk_id

    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        """
        Main movement handler:
          1. Lock shared state
          2. Move within or between chunks
          3. Persist new state & broadcast update
        """
        async with self._lock:
            state = self._state_by_ws[ws]
            board = self._ensure_chunk(state.chunk_id)
            nr, nc = state.pos.row + dr, state.pos.col + dc
            moved, old_chunk_id = False, None

            if self._in_bounds(nr, nc):
                moved = self._apply_move_within_chunk(state, board, nr, nc)
            else:
                direction = self._edge_direction(nr, nc)
                moved, old_chunk_id = self._transfer_between_chunks(ws, state, direction)

            if moved and (pid := self._user_id_by_ws.get(ws)):
                token = MOVE_TOKENS.get((dr, dc), ActionToken.UP)
                append_player_action(pid, state.chunk_id, token)
                save_player_position(pid, state.chunk_id, state.pos.row, state.pos.col)

        if moved:
            await self._post_move_housekeeping(ws, state, old_chunk_id)

    async def _post_move_housekeeping(self, ws: WebSocket,
                                      state: PlayerState,
                                      old_chunk_id: Optional[str] = None) -> None:
        """After successful move, broadcast and maybe show message."""
        if old_chunk_id and old_chunk_id != state.chunk_id:
            await self._broadcast_chunk(old_chunk_id)
        await self._broadcast_chunk(state.chunk_id)
        await self._maybe_send_message_at(ws)

    async def color_plus_plus(self, ws: WebSocket) -> None:
        """Randomly update player color and refresh chunk."""
        async with self._lock:
            state = self._state_by_ws[ws]
            board = self._ensure_chunk(state.chunk_id)
            r2, g2, b2 = (random.randint(0, 3) for _ in range(3))
            new_color = make_color(r2, g2, b2)
            state.color = new_color
            state.underlying_cell = new_color
            board[state.pos.row, state.pos.col] = with_player(new_color)
            save_chunk(state.chunk_id, board)
            if (pid := self._user_id_by_ws.get(ws)):
                append_player_action(pid, state.chunk_id, ActionToken.COLOR)
        await self._broadcast_chunk(state.chunk_id)

    # --------------------------------------------------------------------
    # Messaging
    # --------------------------------------------------------------------

    async def _broadcast_chunk(self, chunk_id: str) -> None:
        """Send board update to all connected watchers."""
        async with self._lock:
            board = self._ensure_chunk(chunk_id)
            payload: MatrixPayload = {
                "type": "matrix",
                "w": W, "h": H,
                "data": board.flatten().tolist(),
                "chunk_id": chunk_id,
                "total_players": len(self._sockets),
            }
            dead: Set[WebSocket] = set()
            for ws in list(self._chunk_watchers.get(chunk_id, set())):
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception as e:
                    dead.add(ws)
                    logger.debug(f"Send failed for watcher: {e}")
            for ws in dead:
                await self.disconnect(ws)

    async def _maybe_send_message_at(self, ws: WebSocket) -> None:
        """If player stands on a hidden message, show it."""
        state = self._state_by_ws.get(ws)
        if not state:
            return
        board = self._ensure_chunk(state.chunk_id)
        cell_under = state.underlying_cell or without_player(board[state.pos.row, state.pos.col])

        if get_bit(cell_under, BIT_HAS_LINK):
            current_pos = (state.chunk_id, state.pos.row, state.pos.col)
            if self._last_msg_pos_by_ws.get(ws) == current_pos:
                return
            msg = load_message(state.chunk_id, state.pos.row, state.pos.col)
            if msg:
                try:
                    await ws.send_text(json.dumps({"type": "message", "data": msg}))
                except Exception as e:
                    logger.debug(f"Failed to send message: {e}")
                self._last_msg_pos_by_ws[ws] = current_pos
        else:
            self._last_msg_pos_by_ws[ws] = None

    async def write_message(self, ws: WebSocket, content: str) -> None:
        """Allow player to hide a message at their current location."""
        async with self._lock:
            state = self._state_by_ws[ws]
            board = self._ensure_chunk(state.chunk_id)
            existing = load_message(state.chunk_id, state.pos.row, state.pos.col)
            if existing or get_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK):
                await ws.send_text(json.dumps({
                    "type": "error", "code": "SPACE_OCCUPIED",
                    "message": "This spot already has a message!"
                }))
                return
            message = Message(
                content=content,
                author=self._user_id_by_ws.get(ws) or "unknown",
                chunk_id=state.chunk_id,
                position=(state.pos.row, state.pos.col)
            )
            save_message(message)
            board[state.pos.row, state.pos.col] = set_bit(board[state.pos.row, state.pos.col], BIT_HAS_LINK, True)
            state.underlying_cell = set_bit(state.underlying_cell, BIT_HAS_LINK, True)
            save_chunk(state.chunk_id, board)

        await self._broadcast_chunk(state.chunk_id)
        notice = json.dumps({"type": "announcement", "data": {"text": "A player hid a treasure"}})
        for target_ws in list(self._chunk_watchers.get(state.chunk_id, set())):
            try:
                await target_ws.send_text(notice)
            except Exception as e:
                logger.debug(f"Announcement failed: {e}")
   