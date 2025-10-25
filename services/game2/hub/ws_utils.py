import json
import logging
from typing import Any, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketUtils:
    """Helper functions for safely sending JSON over WebSockets."""

    @staticmethod
    async def send_json(ws: WebSocket, payload: Any) -> bool:
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as e:
            logger.debug(f"send_json failed: {e}")
            return False

    @staticmethod
    async def fanout_text(watchers: Set[WebSocket], text: str) -> Set[WebSocket]:
        """Send text to all watchers, return sockets that failed."""
        dead: Set[WebSocket] = set()
        for ws in list(watchers):
            try:
                await ws.send_text(text)
            except Exception:
                dead.add(ws)
        return dead
