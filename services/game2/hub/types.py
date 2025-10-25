import torch
from typing import Dict,Tuple, Literal, TypedDict
from dataclasses import dataclass
from ..data.db_history import  ActionToken


@dataclass(frozen=True)
class Coord:
    """A coordinate (row, col) on a board."""
    row: int
    col: int

@dataclass
class PlayerState:
    """Holds all runtime state for a connected player."""
    user_id: str
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

class AnnouncementPayload(TypedDict):
    type: Literal["announcement"]
    data: dict

class ErrorPayload(TypedDict):
    type: Literal["error"]
    code: str
    message: str

class IncomingMsg(TypedDict, total=False):
    command : str
    content : str 
   
MOVE_TOKENS: Dict[Tuple[int, int], ActionToken] = {
    (0, 1): ActionToken.RIGHT,
    (0, -1): ActionToken.LEFT,
    (-1, 0): ActionToken.UP,
    (1, 0): ActionToken.DOWN,
}

Direction = Literal["up", "down", "left", "right"]


