from typing import Dict, Optional
from fastapi import WebSocket

from .messages import MessageService
from ..hub.sessions import SessionStore
from ..hub.world import WorldService
from ..hub.chunk_players import ChunkPlayers

class ChatManager:
    """
    High-level chat logic:
    - manages sending, receiving, reactions, typing, etc.
    - uses MessageService for DB actions
    - uses PlayerActionHistory from world for action logging
    """

    def __init__(self, session_store: SessionStore, world: WorldService, message_service: MessageService, chunk_players: ChunkPlayers):
        self.session_store = session_store
        self.world = world
        self.player_actions_history = world.player_actions_history
        self._selected_partner: Dict[str, Optional[str]] = {}
        self.messages = message_service
        self.chunk_players = chunk_players


    def set_selected_partner(self, me: str, other: Optional[str]) -> None:
        self._selected_partner[me] = other

    def get_selected_partner(self, me: str) -> Optional[str]:
        return self._selected_partner.get(me)


    async def broadcast_to_player(self, player_id: str, payload: dict) -> None:
        """
        Send a JSON payload to all sockets of a given player.
        """
        for ws in self.session_store.sockets_for_user(player_id).copy():
            try:
                await ws.send_json(payload)
            except Exception:
                self.session_store.pop(ws)

  
    async def handle_chat(self, ws: WebSocket, kind: str, data: dict, player_id: str):
        """
        Handle all chat WebSocket actions.
        """
        if kind == "select":
            partner = data.get("selectedPlayer")
            self.set_selected_partner(player_id, partner)
            if partner:
                msgs = self.messages.history_between(player_id, partner, viewer=player_id)
                await ws.send_json({"type": "history", "with": partner, "messages": msgs})
            return

        if kind == "typing":
            partner = self.get_selected_partner(player_id)
            if partner:
                await self.broadcast_to_player(partner, {"type": "typing", "typing": [player_id]})
            return

        if kind == "react":
            msg_id = data.get("messageId")
            reaction = data.get("reaction")
            if not msg_id:
                await ws.send_json({"type": "error", "message": "missing messageId"})
                return

            msg = self.messages.get_message_by_id(msg_id)
            if not msg:
                await ws.send_json({"type": "error", "message": "message not found"})
                return

            self.messages.update_reaction(msg_id, reaction)
            await ws.send_json({"type": "react", "messageId": msg_id, "my_reaction": reaction})
            return

        if kind == "message":
            text = data.get("message", "")
            partner = data.get("selectedPlayer") or self.get_selected_partner(player_id)
            if not partner:
                await ws.send_json({"type": "error", "message": "No partner selected"})
                return

            saved = self.messages.append_message(player_id, partner, text, data.get("timestamp"))
            payload = self.messages._minimal_view(saved) | {"type": "message", "sender": player_id, "to": partner}

            await self.broadcast_to_player(partner, payload)

            await ws.send_json({
                "type": "sent",
                "to": partner,
                "id": saved["id"],
                "message": text,
                "timestamp": saved["timestamp"]
            })

            _, session = self.session_store.find_by_user_id(player_id)
            if not session:
                return
            try:
                state = session.state
                board = self.world._chunks.get(state.chunk_id)
                players_now = self.chunk_players.get_players_in_chunk(state.chunk_id)
                self.player_actions_history.record_player_send_message(
                    user_id=player_id,
                    chunk_id=state.chunk_id,
                    board=board,
                    players= players_now
                )
            except Exception as e:
                print(f"[WARN] Failed to record chat action for {player_id}: {e}")
            return

        await ws.send_json({"type": "error", "message": f"unknown type: {kind}"})
