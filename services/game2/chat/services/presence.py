from typing import Dict, Set, Optional
from fastapi import WebSocket

active_players: Dict[str, Set[WebSocket]] = {}
_selected_partner: Dict[str, Optional[str]] = {}

def add_socket(player_id: str, ws: WebSocket):
    active_players.setdefault(player_id, set()).add(ws)
    _selected_partner[player_id] = None

def remove_socket(player_id: str, ws: WebSocket):
    bucket = active_players.get(player_id)
    if bucket:
        bucket.discard(ws)
        if not bucket:
            active_players.pop(player_id, None)
    _selected_partner[player_id] = None

def get_selected(player_id: str) -> Optional[str]:
    return _selected_partner.get(player_id)

def set_selected(player_id: str, partner: Optional[str]):
    _selected_partner[player_id] = partner

async def send_to_all(player_id: str, payload: dict):
    for s in list(active_players.get(player_id, set())):
        try:
            await s.send_json(payload)
        except Exception:
            pass
