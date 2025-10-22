from __future__ import annotations
import os
import json
import logging
import random
from typing import Any, Optional, Tuple, Set

import torch
from fastapi import WebSocket
from jose import jwt, JWTError

from .types import Coord, PlayerState, Direction
from ..core.settings import W, H, DTYPE, BIT_HAS_LINK, BIT_IS_PLAYER
from ..core.bits import get_bit
from ..core.ids import chunk_id_from_coords, coords_from_chunk_id

logger = logging.getLogger(__name__)
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "CHANGE_ME_123456789")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

def is_empty(board: torch.Tensor, r: int, c: int) -> bool:
    return int(get_bit(board[r, c], BIT_IS_PLAYER)) == 0

def neighbor_chunk_id(chunk_id: str, direction: Direction) -> str:
    cx, cy = coords_from_chunk_id(chunk_id)
    if direction == "up":
        cy -= 1
    elif direction == "down":
        cy += 1
    elif direction == "left":
        cx -= 1
    elif direction == "right":
        cx += 1
    return chunk_id_from_coords(cx, cy)

def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < H and 0 <= c < W

def edge_direction(nr: int, nc: int) -> Direction:
    if nr < 0:
        return "up"
    if nr >= H:
        return "down"
    if nc < 0:
        return "left"
    return "right"

def edge_target_for_direction(state: PlayerState, direction: Direction) -> Coord:
    if direction == "up":
        return Coord(H - 1, state.pos.col)
    if direction == "down":
        return Coord(0, state.pos.col)
    if direction == "left":
        return Coord(state.pos.row, W - 1)
    return Coord(state.pos.row, 0)

def random_empty_cell(board: torch.Tensor) -> Coord:
    for _ in range(4096):
        r, c = random.randrange(H), random.randrange(W)
        if is_empty(board, r, c):
            return Coord(r, c)
        return Coord(H // 2, W // 2)

def extract_token(ws: WebSocket) -> Optional[str]:
    token = ws.query_params.get("token")
    if token:
        return token
    auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
    if isinstance(auth, str) and auth.lower().startswith("bearer "):
        return auth[7:]
    return None  

def verify_token_or_reason(token: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    if not token:
        return False, "no token provided", None
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

async def send_json(ws: WebSocket, payload: Any) -> bool:
    try:
        await ws.send_text(json.dumps(payload, ensure_ascii=False))
        return True
    except Exception as e:
        logger.debug(f"send_json failed: {e}")
        return False

async def fanout_text(watchers: Set[WebSocket], text: str) -> Set[WebSocket]:
    dead: Set[WebSocket] = set()
    for ws in list(watchers):
        try:
            await ws.send_text(text)
        except Exception:
            dead.add(ws)
    return dead