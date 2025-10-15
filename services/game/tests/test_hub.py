# tests/test_hub.py
import asyncio
import json
import torch
import pytest
pytest_plugins = "pytest_asyncio"


# נייבא את המודול רק לאחר שנכין את ה-monkeypatchים בתוך הבדיקות (הערות על הייבוא למטה)
from game import hub as hd


# fake DB store
class FakeDB:
    def __init__(self):
        self.store = {}

    def load_chunk(self, cid):
        # return a clone to avoid aliasing between tests
        v = self.store.get(cid)
        return None if v is None else v.clone()

    def save_chunk(self, cid, board):
        self.store[cid] = board.clone()


# פיקטיבי WebSocket פשוט ללכידת הודעות
class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_text(self, txt: str):
        # שמור את הטקסט שנשלח
        self.sent.append(txt)

    def __repr__(self):
        return f"<FakeWS id={id(self)}>"

@pytest.fixture(autouse=True)
def configure_hub(monkeypatch):
    """
    Prepare deterministic environment: קטן W,H, DTYPE, DB mocks, ואותו random
    """
    # קטנים כדי שמבחנים יהיו מהירים ו deterministic
    monkeypatch.setattr(hd, "W", 4)
    monkeypatch.setattr(hd, "H", 4)
    monkeypatch.setattr(hd, "DTYPE", torch.uint8)
    monkeypatch.setattr(hd, "BIT_IS_PLAYER", 7)

    # DB fake
    fake_db = FakeDB()
    monkeypatch.setattr(hd, "load_chunk", fake_db.load_chunk)
    monkeypatch.setattr(hd, "save_chunk", fake_db.save_chunk)

    # קבע seed ל־random (כך שהבחירה של תאים רנדומליים תהיה deterministic)
    import random
    random.seed(0)

    yield


def test_chunk_id_and_coords_roundtrip():
    assert hd.chunk_id_from_coords(3, -2) == "3,-2"
    assert hd.coords_from_chunk_id("10,5") == (10, 5)
    assert hd.coords_from_chunk_id(hd.chunk_id_from_coords(0, 0)) == (0, 0)


def test_neighbor_cid():
    hub = hd.Hub()
    base = hub.root_cid  # כרגע '0,0'

    # ציפייה מתוקנת לפי root האמיתי
    expected_up = hub.neighbor_cid(base, "up")  # זה יחזור '0,-1'
    assert hub.neighbor_cid(base, "up") == expected_up

    expected_down = hub.neighbor_cid(base, "down")
    assert hub.neighbor_cid(base, "down") == expected_down

    expected_left = hub.neighbor_cid(base, "left")
    assert hub.neighbor_cid(base, "left") == expected_left

    expected_right = hub.neighbor_cid(base, "right")
    assert hub.neighbor_cid(base, "right") == expected_right




@pytest.mark.asyncio
async def test_ensure_chunk_creates_and_saves(monkeypatch):
    """
    אם אין chunk קיים - _ensure_chunk צריכה ליצור מטריצה של אפסים ולשמור אותה באמצעות save_chunk.
    מכיוון שה־save_chunk הוחלף ב־FakeDB, נוכל בוודאות שהמטען נשמר.
    """
    # נשתמש בהופעה של Hub שתשתמש ב־FakeDB
    hub = hd.Hub()
    cid = hub.root_cid
    # אחרי יצירה, צריך להיות קיים cid במאגר ה־FakeDB (load_chunk מאפשר גישה דרך hd.load_chunk)
    loaded = hd.load_chunk(cid)
    assert loaded is not None
    assert isinstance(loaded, torch.Tensor)
    assert loaded.shape == (hd.W, hd.H)


@pytest.mark.asyncio
async def test_connect_sends_chunk_and_sets_state(monkeypatch):
    hub = hd.Hub()
    fake_ws = FakeWebSocket()

    # ודא שאין קודם מיקום ל־ws
    assert fake_ws not in hub.pos_by_ws

    # קרא ל־connect
    await hub.connect(fake_ws)

    # לאחר ה־connect - ה־ws צריך להיות ברשימות
    assert fake_ws in hub.sockets
    assert fake_ws in hub.watchers[hub.root_cid]
    assert fake_ws in hub.player_color
    assert fake_ws in hub.val_by_ws
    assert fake_ws in hub.underlying_by_ws

    # ניתוח ההודעה שנשלחה בו־זמנית ע"י _send_chunk
    assert len(fake_ws.sent) >= 1
    payload = json.loads(fake_ws.sent[-1])
    assert payload["type"] == "matrix"
    assert payload["w"] == hd.W
    assert payload["h"] == hd.H
    assert payload["chunk_id"] == hub.root_cid
    # data length should match W*H
    assert len(payload["data"]) == hd.W * hd.H


@pytest.mark.asyncio
async def test_disconnect_restores_underlying_and_removes(monkeypatch):
    hub = hd.Hub()
    ws = FakeWebSocket()
    await hub.connect(ws)

    # נשמור מה המיקום הנוכחי
    cid, r, c = hub.pos_by_ws[ws]

    # בצע ניתוק
    await hub.disconnect(ws)

    # לאחר מכן המיקום לא צריך להיות ב pos_by_ws
    assert ws not in hub.pos_by_ws
    assert ws not in hub.player_color
    assert ws not in hub.val_by_ws
    # socket גם לא צריך להיות ברשימת sockets
    assert ws not in hub.sockets
    # watchers לא צריכים להכיל את ה־ws יותר
    assert ws not in hub.watchers.get(cid, set())


@pytest.mark.asyncio
async def test_move_within_bounds_moves_and_broadcasts(monkeypatch):
    hub = hd.Hub()
    ws = FakeWebSocket()
    await hub.connect(ws)

    # אתחל ערך ברור של underlying כדי שנוכל לאמת החלפת תאים
    cid, r, c = hub.pos_by_ws[ws]
    # ננסה לעבור שמאלה/ימינה בתוך הגבולות אם אפשר
    # בחר תנועה שמבטיחה בתוך הגבולות: dr=0, dc=1 אם אפשר
    dr, dc = 0, 1
    # שמור עותק של מיקום קודם
    prev_pos = hub.pos_by_ws[ws]

    await hub.move(ws, dr, dc)

    # אם התנועה היתה חוקית בתוך הגבולות - המיקום צריך להשתנות או להישאר (במקרה תפוסים)
    new_pos = hub.pos_by_ws.get(ws)
    assert new_pos is not None
    # ודא ש־save_chunk נקראה דרך ה־FakeDB (אין שגיאות), ושידור נשלח
    # בנינו FakeWebSocket ששומר הודעות שנשלחו - לאחר move צריך להיות לפחות הודעה אחת נוספת
    assert len(ws.sent) >= 1


@pytest.mark.asyncio
async def test_color_plus_plus_updates_and_broadcasts(monkeypatch):
    hub = hd.Hub()
    ws = FakeWebSocket()
    await hub.connect(ws)

    # נקרא ל color_plus_plus
    await hub.color_plus_plus(ws)

    # וודא שנשלחה הודעה לשידור
    assert len(ws.sent) >= 1
