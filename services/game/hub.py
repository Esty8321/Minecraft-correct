from typing import Tuple, Dict, Set
import asyncio, json, random
import torch
from fastapi import WebSocket

from .settings import BIT_HAS_LINK, W, H, DTYPE, BIT_IS_PLAYER
from .bits import set_bit, get_bit, inc_color, make_color, with_player, without_player
from .ids import chunk_id_from_coords, coords_from_chunk_id
from .db import load_message, save_chunk, load_chunk, save_message
from .models import Message


class Hub:
    def __init__(self) -> None:
        self.chunks: Dict[str, torch.Tensor] = {}
        self.watchers: Dict[str, Set[WebSocket]] = {}
        self.root_cid = chunk_id_from_coords(0, 0)
        self._ensure_chunk(self.root_cid)

        self.sockets: Set[WebSocket] = set()
        self.pos_by_ws: Dict[WebSocket, Tuple[str, int, int]] = {}
        self.val_by_ws: Dict[WebSocket, torch.Tensor] = {}
        self.player_color: Dict[WebSocket, torch.Tensor] = {}

        self.underlying_by_ws: Dict[WebSocket, torch.Tensor] = {}
        self.last_msg_at: Dict[WebSocket, Tuple[str, int, int] | None] = {}

        self.lock = asyncio.Lock()

    def _ensure_chunk(self, cid: str) -> torch.Tensor:
        if cid in self.chunks:
            return self.chunks[cid]
        loaded = load_chunk(cid)
        if loaded is None:
            loaded = torch.zeros((W, H), dtype=DTYPE)
            save_chunk(cid, loaded)
        self.chunks[cid] = loaded
        return loaded

    def _is_empty(self, board: torch.Tensor, r: int, c: int) -> bool:
        return int(get_bit(board[r, c], BIT_IS_PLAYER)) == 0

    def _random_empty_cell(self, board: torch.Tensor) -> Tuple[int, int]:
        for _ in range(4096):
            r = random.randrange(H)
            c = random.randrange(W)
            if self._is_empty(board, r, c):
                return r, c
        return H // 2, W // 2

    def neighbor_cid(self, cid: str, direction: str) -> str:
        cx, cy = coords_from_chunk_id(cid)
        if direction == "up":
            cy -= 1
        if direction == "down":
            cy += 1
        if direction == "left":
            cx -= 1
        if direction == "right":
            cx += 1
        return chunk_id_from_coords(cx, cy)

    # ---------- חיבור / ניתוק ----------

    async def connect(self, ws: WebSocket) -> None:
        self.sockets.add(ws)
        async with self.lock:
            cid = self.root_cid
            board = self._ensure_chunk(cid)
            r, c = self._random_empty_cell(board)

            pr = random.randint(0, 3)
            pg = random.randint(0, 3)
            pb = random.randint(0, 3)
            pcolor = make_color(pr, pg, pb)
            self.player_color[ws] = pcolor

            underlying = without_player(board[r, c])
            self.underlying_by_ws[ws] = underlying

            board[r, c] = with_player(pcolor)
            save_chunk(cid, board)
            self.val_by_ws[ws] = with_player(pcolor).clone()
            self.pos_by_ws[ws] = (cid, r, c)

            if cid not in self.watchers:
                self.watchers[cid] = set()
            self.watchers[cid].add(ws)

        await self._broadcast_chunk(cid)

    async def disconnect(self, ws: WebSocket) -> None:
        cid = None
        async with self.lock:
            if ws in self.pos_by_ws:
                cid, r, c = self.pos_by_ws.pop(ws)
                board = self._ensure_chunk(cid)
                underlying = self.underlying_by_ws.pop(ws, torch.tensor(0, dtype=DTYPE))
                board[r, c] = underlying
                save_chunk(cid, board)
                self.watchers.get(cid, set()).discard(ws)
                await self._broadcast_chunk(cid)

            self.val_by_ws.pop(ws, None)
            self.player_color.pop(ws, None)

        self.sockets.discard(ws)

        if cid is not None:
            await self._broadcast_chunk(cid)


    async def move(self, ws: WebSocket, dr: int, dc: int) -> None:
        async with self.lock:
            cid, r, c = self.pos_by_ws[ws]
            board = self._ensure_chunk(cid)
            pcolor = self.player_color[ws]

            nr, nc = r + dr, c + dc

            # --- (א) תזוזה בתוך אותו צ'אנק ---
            if 0 <= nr < H and 0 <= nc < W:
                if self._is_empty(board, nr, nc):
                    # מחזירים את ה-underlying הישן לתא שעוזבים
                    old_under = self.underlying_by_ws[ws]
                    board[r, c] = old_under

                    # מוציאים את השחקן מהתא יעד ושומרים את ה-underlying החדש
                    dest_cell_before = board[nr, nc]
                    new_under = without_player(dest_cell_before)
                    self.underlying_by_ws[ws] = new_under

                    # מציירים שחקן ביעד, ובמידה ולתא היה ביט הודעה - משאירים אותו גם על התצוגה
                    new_vis = with_player(pcolor)
                    if get_bit(dest_cell_before, BIT_HAS_LINK):
                        new_vis = set_bit(new_vis, BIT_HAS_LINK, True)

                    board[nr, nc] = new_vis
                    self.pos_by_ws[ws] = (cid, nr, nc)
                    save_chunk(cid, board)
                    await self._broadcast_chunk(cid)
                    await self._maybe_send_message_at(ws)

                return

            # --- (ב) מעבר לצ'אנק שכן ---
            direction = None
            if nr < 0:
                direction = "up"
            elif nr >= H:
                direction = "down"
            elif nc < 0:
                direction = "left"
            elif nc >= W:
                direction = "right"

            new_cid = self.neighbor_cid(cid, direction or "right")
            new_board = self._ensure_chunk(new_cid)

            if direction == "up":
                tr, tc = H - 1, c
            elif direction == "down":
                tr, tc = 0, c
            elif direction == "left":
                tr, tc = r, W - 1
            else:
                tr, tc = r, 0

            if self._is_empty(new_board, tr, tc):
                # מחזירים את ה-underlying הישן לתא שעזבנו בצ'אנק הישן
                old_under = self.underlying_by_ws[ws]
                board[r, c] = old_under
                save_chunk(cid, board)

                # מוציאים את השחקן מהתא יעד בצ'אנק החדש ושומרים underlying
                dest_cell_before = new_board[tr, tc]
                new_under = without_player(dest_cell_before)
                self.underlying_by_ws[ws] = new_under

                # מציירים שחקן ביעד, ושומרים את ביט ההודעה אם היה בתא
                new_vis = with_player(pcolor)
                if get_bit(dest_cell_before, BIT_HAS_LINK):
                    new_vis = set_bit(new_vis, BIT_HAS_LINK, True)

                new_board[tr, tc] = new_vis
                save_chunk(new_cid, new_board)

                self.pos_by_ws[ws] = (new_cid, tr, tc)
                self.watchers[cid].discard(ws)
                self.watchers.setdefault(new_cid, set()).add(ws)

                await self._broadcast_chunk(cid)
                await self._broadcast_chunk(new_cid)
                await self._maybe_send_message_at(ws)



    


    async def color_plus_plus(self, ws: WebSocket) -> None:
        print("[INFO] in color_plus_plus function")
        async with self.lock:
            cid, r, c = self.pos_by_ws[ws]
            board = self._ensure_chunk(cid)

            pr = random.randint(0, 3)
            pg = random.randint(0, 3)
            pb = random.randint(0, 3)
            new_color = make_color(pr, pg, pb)

            self.underlying_by_ws[ws] = new_color
            board[r, c] = with_player(new_color)
            save_chunk(cid, board)

        await self._broadcast_chunk(cid)

    async def _send_chunk(self, ws: WebSocket) -> None:
        if ws not in self.pos_by_ws:
            return
        cid, _, _ = self.pos_by_ws[ws]
        board = self._ensure_chunk(cid)
        total_players = len(self.sockets)
        payload = {
            "type": "matrix",
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": cid,
            "total_players": total_players,
        }
        await ws.send_text(json.dumps(payload))

    async def _broadcast_chunk(self, cid: str) -> None:
        board = self._ensure_chunk(cid)
        total_players = len(self.sockets)

        payload = {
            "type": "matrix",
            "w": W,
            "h": H,
            "data": board.flatten().tolist(),
            "chunk_id": cid,
            "total_players": total_players,
        }

        dead: Set[WebSocket] = set()
        for s in list(self.watchers.get(cid, set())):
            try:
                await s.send_text(json.dumps(payload))
            except Exception as e:
                dead.add(s)
                print("[HUB] failed to send text to client", e)

        for s in dead:
            try:
                await self.disconnect(s)
            except Exception as e:
                print("[HUB] failed to disconnect dead socket", e)
    

    # async def write_message(self, ws: WebSocket, content: str) -> None:
    #     async with self.lock:
    #         try:
    #             chunk_id, row, col = self.pos_by_ws[ws]
    #             board = self._ensure_chunk(chunk_id)

    #             # דאבל־בדיקה: גם ב־DB וגם בביט על הלוח
    #             existing = load_message(chunk_id, row, col)
    #             if existing or get_bit(board[row, col], BIT_HAS_LINK):
    #                 await ws.send_text(json.dumps({
    #                     "type": "error",
    #                     "code": "SPACE_OCCUPIED",
    #                     "message": "This spot already has a message!"
    #                 }))
    #                 return

    #             message = Message(
    #                 content=content,
    #                 author=str(id(ws)),
    #                 chunk_id=chunk_id,
    #                 position=(row, col),
    #             )

    #             # שומר הודעה ומסמן ביט על התא
    #             save_message(message)
    #             board[row, col] = set_bit(board[row, col], BIT_HAS_LINK, True)

    #             # סינכרון קריטי: לעדכן גם את ה-underlying כדי שלא יימחק כשנזוז
    #             if ws in self.underlying_by_ws:
    #                 self.underlying_by_ws[ws] = set_bit(self.underlying_by_ws[ws], BIT_HAS_LINK, True)

    #             save_chunk(chunk_id, board)

    #         except Exception as e:
    #             print(f"[ERROR] Failed to write message: {e}")
    #             try:
    #                 await ws.send_text(json.dumps({"type": "error", "message": "Failed to save message"}))
    #             except:
    #                 pass
    #             return

    #     # מחוץ לנעילה – שידור ועדכון לקליינטים
    #     await self._broadcast_chunk(chunk_id)

    #     payload = json.dumps({"type": "message", "data": message.to_dict()})
    #     try:
    #         await ws.send_text(payload)
    #     except Exception as e:
    #         print("[HUB] failed to send message to author", e)

    #     for other_ws in self.watchers.get(chunk_id, set()):
    #         if other_ws is ws:
    #             continue
    #         try:
    #             await other_ws.send_text(payload)
    #         except Exception as e:
    #             print("[HUB] failed to send message to peer", e)
    
    async def _maybe_send_message_at(self, ws: WebSocket) -> None:
        if ws not in self.pos_by_ws:
            return
        chunk_id, row, col = self.pos_by_ws[ws]
        board = self._ensure_chunk(chunk_id)

        cell_under = self.underlying_by_ws.get(ws)
        if cell_under is None:
            cell_under = without_player(board[row, col])

        if get_bit(cell_under, BIT_HAS_LINK):
            last = self.last_msg_at.get(ws)
            if last == (chunk_id, row, col):
                return  # אל תחזור על אותה הודעה שוב ושוב
            message = load_message(chunk_id, row, col)
            if message:
                await ws.send_text(json.dumps({"type": "message", "data": message}))
                self.last_msg_at[ws] = (chunk_id, row, col)
        else:
            self.last_msg_at[ws] = None
    async def write_message(self, ws: WebSocket, content: str) -> None:
        async with self.lock:
            try:
                chunk_id, row, col = self.pos_by_ws[ws]
                board = self._ensure_chunk(chunk_id)

                existing = load_message(chunk_id, row, col)
                if existing or get_bit(board[row, col], BIT_HAS_LINK):
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "code": "SPACE_OCCUPIED",
                        "message": "This spot already has a message!"
                    }))
                    return

                message = Message(
                    content=content,
                    author=str(id(ws)),
                    chunk_id=chunk_id,
                    position=(row, col),
                )
                save_message(message)

                board[row, col] = set_bit(board[row, col], BIT_HAS_LINK, True)

                if ws in self.underlying_by_ws:
                    self.underlying_by_ws[ws] = set_bit(self.underlying_by_ws[ws], BIT_HAS_LINK, True)

                save_chunk(chunk_id, board)

            except Exception as e:
                print(f"[ERROR] Failed to write message: {e}")
                try:
                    await ws.send_text(json.dumps({"type": "error", "message": "Failed to save message"}))
                except:
                    pass
                return

        await self._broadcast_chunk(chunk_id)

        notice = json.dumps({
            "type": "announcement",
            "data": { "text": "A player hid a treasure" }
        })
        for target_ws in list(self.watchers.get(chunk_id, set())):
            try:
                await target_ws.send_text(notice)
            except Exception as e:
                print("[HUB] failed to send announcement", e)



        