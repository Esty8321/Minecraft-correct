import pytest, json, asyncio
from unittest.mock import AsyncMock, patch, ANY
from fastapi.testclient import TestClient
from services.game.main import app, hub

client = TestClient(app)

@pytest.mark.asyncio
async def test_startup_and_shutdown_events():
    # Mock clear_player_bits_all כ־AsyncMock
    with patch("services.game.main.clear_player_bits_all", new_callable=AsyncMock) as mock_clear:
        await app.router.startup()
        mock_clear.assert_awaited_once()  # עכשיו נקרא await

    # Mock disconnect לכל ה־ws
    fake_ws = AsyncMock()
    hub.pos_by_ws = {fake_ws: None}

    # Mock hub.disconnect כדי לוודא שנקרא await
    hub.disconnect = AsyncMock()
    await app.router.shutdown()
    hub.disconnect.assert_awaited_once_with(fake_ws)


@pytest.mark.asyncio
async def test_ws_connect_move_color(monkeypatch):
    # Mock hub methods
    monkeypatch.setattr(hub, "connect", AsyncMock())
    monkeypatch.setattr(hub, "move", AsyncMock())
    monkeypatch.setattr(hub, "color_plus_plus", AsyncMock())
    monkeypatch.setattr(hub, "_send_chunk", AsyncMock())
    monkeypatch.setattr(hub, "disconnect", AsyncMock())

    with client.websocket_connect("/ws") as websocket:
        # hub.connect אמור להיקרא
        hub.connect.assert_awaited_once()

        # simulate arrowup key press
        websocket.send_text(json.dumps({"k": "ArrowUp"}))
        await asyncio.sleep(0)  # חובה כדי לאפשר ל-loop הריצה של ה-await
        hub.move.assert_awaited_with(ANY, -1, 0)

        # simulate color++ key press
        websocket.send_text(json.dumps({"k": "color++"}))
        await asyncio.sleep(0)
        hub.color_plus_plus.assert_awaited_with(ANY)
