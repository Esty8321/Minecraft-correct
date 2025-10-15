# from typing import Tuple, Dict, Set
# import asyncio, json, random
# import torch
# from fastapi import WebSocket

# from .settings import BIT_HAS_LINK, W, H, DTYPE, BIT_IS_PLAYER
# from .bits import set_bit, get_bit, inc_color, make_color, with_player, without_player
# from .ids import chunk_id_from_coords, coords_from_chunk_id

# from .db import load_message, save_chunk, load_chunk, save_message 
# from .models import Message
# class Hub:
#     def __init__(self)->None:
#         self.chunks: Dict[str, torch.Tensor] = {}
#         self.watchers: Dict[str, Set[WebSocket]] = {}
#         self.root_cid = chunk_id_from_coords(0, 0)
#         self._ensure_chunk(self.root_cid)
#         self.sockets: Set[WebSocket] = set()
#         self.pos_by_ws : Dict[WebSocket, Tuple[str,int, int]] = {}
#         self.val_by_ws :  Dict[WebSocket, torch.Tensor] = {}
#         self.player_color: Dict[WebSocket, torch.Tensor] = {}
#         self.underlying_by_ws: Dict[WebSocket, torch.Tensor] = {}
#         self.lock = asyncio.Lock()

#     def _ensure_chunk(self, cid: str)-> torch.Tensor:
#         if cid in self.chunks:
#             return self.chunks[cid]
#         loaded = load_chunk(cid)
#         if loaded is None:
#             loaded = torch.zeros((W, H), dtype=DTYPE)
#             save_chunk(cid, loaded)
#         self.chunks[cid] = loaded
#         return loaded

#     def _is_empty(self, board: torch.Tensor, r: int, c:int) ->bool:
#         return int(get_bit(board[r,c], BIT_IS_PLAYER)) == 0
    
#     def _random_empty_cell(self, board: torch.Tensor)->Tuple[int, int]:
#         for _ in range(4096):
#             r = random.randrange(H)
#             c = random.randrange(W)
#             if self._is_empty(board, r,c):
#                 return r,c
#         return H // 2, W // 2
    
#     def neighbor_cid(self, cid: str, direction: str) ->str:
#         cx, cy = coords_from_chunk_id(cid)
#         if direction == "up": cy -= 1
#         if direction == "down":  cy += 1
#         if direction == "left":  cx -= 1
#         if direction == "right": cx += 1
#         return chunk_id_from_coords(cx, cy)
    
#     async def connect(self, ws: WebSocket)->None:
#         self.sockets.add(ws)
#         async with self.lock:
#             cid = self.root_cid
#             board = self._ensure_chunk(cid)
#             r, c = self._random_empty_cell(board)
 
#             pr = random.randint(0, 3)
#             pg = random.randint(0, 3)
#             pb = random.randint(0, 3)
#             pcolor = make_color(pr, pg, pb)
#             self.player_color[ws] = pcolor

#             underlying = without_player(board[r, c])
#             self.underlying_by_ws[ws] = underlying

#             board[r, c] = with_player(pcolor)
#             save_chunk(cid, board)
#             self.val_by_ws[ws]= with_player(pcolor).clone()
#             self.pos_by_ws[ws] = (cid, r, c)
#             # self.watchers[cid].add(ws)
#             if cid not in self.watchers:
#                 self.watchers[cid] = set()
#             self.watchers[cid].add(ws)

        
#         await self._broadcast_chunk(cid)

#     async def disconnect(self, ws: WebSocket)->None:
#         cid = None
#         async with self.lock:
#             if ws in self.pos_by_ws:
#                 cid, r, c = self.pos_by_ws.pop(ws)
#                 board = self._ensure_chunk(cid)
#                 underlying = self.underlying_by_ws.pop(ws, torch.tensor(0, dtype=DTYPE))
#                 board[r, c] = underlying
#                 save_chunk(cid, board)
#                 self.watchers.get(cid, set()).discard(ws)
#                 await self._broadcast_chunk(cid)
            
#             self.val_by_ws.pop(ws, None)
#             self.player_color.pop(ws, None)
#         self.sockets.discard(ws)
        
#         if cid is not None:
#             await self._broadcast_chunk(cid)



#     async def move(self, ws: WebSocket, dr: int, dc : int)->None:
#         async with self.lock:
#             cid, r, c, = self.pos_by_ws[ws]
#             board = self._ensure_chunk(cid)
#             pcolor = self.player_color[ws]

#             nr, nc = r + dr, c + dc
#             if 0 <= nr < H and 0<= nc < W:
#                 if self._is_empty(board, nr, nc):
#                     old_under = self.underlying_by_ws[ws]
#                     board[r, c] = old_under
#                     new_under = without_player(board[nr, nc])
#                     self.underlying_by_ws[ws] = new_under
#                     board[nr, nc] = with_player(pcolor)
#                     self.pos_by_ws[ws] = (cid, nr, nc)
#                     save_chunk(cid, board)
#                     await self._broadcast_chunk(cid)
#                 return 
            
#             direction = None
#             if nr < 0:        direction = "up"
#             elif nr >= H:     direction = "down"
#             elif nc < 0:      direction = "left"
#             elif nc >= W:     direction = "right"
            
#             new_cid = self.neighbor_cid(cid, direction or "right")
#             new_board = self._ensure_chunk(new_cid)
#             if direction == "up":
#                 tr, tc = H - 1, c
#             elif direction == "down":
#                 tr, tc = 0, c
#             elif direction == "left":
#                 tr, tc = r, W - 1
#             else:
#                 tr, tc = r, 0

#             if self._is_empty(new_board, tr, tc):
#                 old_under = self.underlying_by_ws[ws]
#                 board[r, c] = old_under
#                 save_chunk(cid, board)
#                 new_under = without_player(new_board[tr, tc])
#                 self.underlying_by_ws[ws] = new_under
#                 new_board[tr, tc] = with_player(pcolor)
#                 save_chunk(new_cid, new_board)
#                 self.pos_by_ws[ws] = (new_cid, tr, tc)
#                 self.watchers[cid].discard(ws)
#                 self.watchers.setdefault(new_cid, set()).add(ws)
#                 await self._broadcast_chunk(cid)
#                 await self._broadcast_chunk(new_cid)

            
#     async def color_plus_plus(self, ws: WebSocket) -> None:
#         print('[INFO] in color_plus_plus funcion')
#         async with self.lock:
#             cid, r, c = self.pos_by_ws[ws]
#             board = self._ensure_chunk(cid)
            
#             pr = random.randint(0, 3)
#             pg = random.randint(0, 3)
#             pb = random.randint(0, 3)
#             new_color = make_color(pr, pg, pb)

#             # under = self.underlying_by_ws.get(ws, torch.tensor(0, dtype = DTYPE))
#             # under = inc_color(under)
#             self.underlying_by_ws[ws] = new_color
#             board[r, c] = with_player(new_color)
#             save_chunk(cid, board)
#         await self._broadcast_chunk(cid)

#     async def _send_chunk(self, ws: WebSocket)->None:
#         if ws not in self.pos_by_ws:
#             return 
#         cid, _, _ = self.pos_by_ws[ws]
#         board = self._ensure_chunk(cid)
#         total_players = len(self.sockets)
#         payload = {
#             "type": "matrix",
#             "w": W, "h": H,
#             "data": board.flatten().tolist(),
#             "chunk_id": cid,
#             "total_players":total_players,            
#         }
#         await ws.send_text(json.dumps(payload))
    
#     async def _broadcast_chunk(self, cid: str)->None:
#         board = self._ensure_chunk(cid)
#         total_players = len(self.sockets)
       
#         payload = {
#             "type": "matrix",
#             "w": W, "h": H,
#             "data": board.flatten().tolist(),
#             "chunk_id": cid,
#             "total_players":total_players
#         }

#         dead: Set[WebSocket] = set()
#         for s in list(self.watchers.get(cid, set())):
#             try:
#                 await s.send_text(json.dumps(payload))
#             except Exception as e:
#                 dead.add(s)
#                 print('[HUB] failed to send text to client',e)
#         for s in dead:
#             try:
#                 await self.disconnect(s)
#             except Exception as e:
#                 print('[HUB] failed to disconnect dead socket', e)



# def chunk_id_from_coords(cx: int, cy: int)->str:
#     return f"{cx},{cy}"

# def coords_from_chunk_id(cid: str)->Tuple[int, int]:
#     a, b = cid.split(",")
#     return int(a), int(b)

# async def write_message(self, ws: WebSocket, content: str) -> None:
#         """Handle writing a new message at player's current position"""
#         async with self.lock:
#             try:
#                 # Get player position
#                 chunk_id, row, col = self.pos_by_ws[ws]
#                 board = self._ensure_chunk(chunk_id)
#                 print(f"[game] write_message at {chunk_id} ({row},{col}) content={content!r}")
#                 has_link = int(get_bit(board[row, col], BIT_HAS_LINK))
#                 print(f"[game] cell.has_link={has_link}")   # <–– האם התא תפוס כבר?

#                 # Check if spot is already taken
#                 if get_bit(board[row, col], BIT_HAS_LINK):
#                     await ws.send_text(json.dumps({
#                         "type": "error",
#                         "code": "SPACE_OCCUPIED",
#                         "message": "This spot already has a message!"
#                     }))
#                     return

#                 # Create new message
#                 message = Message(
#                     content=content,
#                     author=str(id(ws)),  # or username if available
#                     chunk_id=chunk_id,
#                     position=(row, col)
#                 )
                
#                 # Save message and update board
#                 save_message(message)
#                 board[row, col] = set_bit(board[row, col], BIT_HAS_LINK, True)
#                 save_chunk(chunk_id, board)
                
#                 # Broadcast to all users in chunk
#                 await self._broadcast_chunk(chunk_id)
                
#                 # Send message data to everyone
#                 msg_data = json.dumps({
#                     "type": "message",
#                     "data": message.to_dict()
#                 })
                
#                 # Send to message author
#                 await ws.send_text(msg_data)
                
#                 # Send to other users in same chunk
#                 for other_ws in self.watchers.get(chunk_id, set()):
#                     if other_ws != ws:
#                         await other_ws.send_text(msg_data)

#             except Exception as e:
#                 print(f"[ERROR] Failed to write message: {e}")
#                 await ws.send_text(json.dumps({
#                     "type": "error",
#                     "message": "Failed to save message"
#                 }))

# async def check_for_message(self, ws: WebSocket) -> None:
#         """בודק אם יש הודעה במיקום הנוכחי ושולח אותה למשתמש"""
#         chunk_id, row, col = self.pos_by_ws[ws]
#         board = self._ensure_chunk(chunk_id)
        
#         # בודק אם יש הודעה במיקום (ביט 1)
#         if get_bit(board[row, col], BIT_HAS_LINK):
#             # טוען את ההודעה מה-JSON
#             message = load_message(chunk_id, row, col)
#             if message:
#                 # שולח למשתמש
#                 await ws.send_text(json.dumps({
#                     "type": "message",
#                     "data": message
#                 }))


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
            if 0 <= nr < H and 0 <= nc < W:
                if self._is_empty(board, nr, nc):
                    old_under = self.underlying_by_ws[ws]
                    board[r, c] = old_under
                    new_under = without_player(board[nr, nc])
                    self.underlying_by_ws[ws] = new_under
                    board[nr, nc] = with_player(pcolor)
                    self.pos_by_ws[ws] = (cid, nr, nc)
                    save_chunk(cid, board)
                    await self._broadcast_chunk(cid)
                return

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
                old_under = self.underlying_by_ws[ws]
                board[r, c] = old_under
                save_chunk(cid, board)

                new_under = without_player(new_board[tr, tc])
                self.underlying_by_ws[ws] = new_under
                new_board[tr, tc] = with_player(pcolor)
                save_chunk(new_cid, new_board)

                self.pos_by_ws[ws] = (new_cid, tr, tc)
                self.watchers[cid].discard(ws)
                self.watchers.setdefault(new_cid, set()).add(ws)

                await self._broadcast_chunk(cid)
                await self._broadcast_chunk(new_cid)

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


    async def write_message(self, ws: WebSocket, content: str) -> None:
        """יצירת הודעה בתא הנוכחי של השחקן ושידורה לכל הצופים בצ'אנק"""
        async with self.lock:
            try:
                chunk_id, row, col = self.pos_by_ws[ws]
                board = self._ensure_chunk(chunk_id)

                if get_bit(board[row, col], BIT_HAS_LINK):
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "code": "SPACE_OCCUPIED",
                                "message": "This spot already has a message!",
                            }
                        )
                    )
                    return

                message = Message(
                    content=content,
                    author=str(id(ws)),  # אפשר להחליף לשם משתמש אם יש
                    chunk_id=chunk_id,
                    position=(row, col),
                )

                save_message(message)
                board[row, col] = set_bit(board[row, col], BIT_HAS_LINK, True)
                save_chunk(chunk_id, board)

            except Exception as e:
                print(f"[ERROR] Failed to write message: {e}")
                try:
                    await ws.send_text(
                        json.dumps(
                            {"type": "error", "message": "Failed to save message"}
                        )
                    )
                except:
                    pass
                return

        await self._broadcast_chunk(chunk_id)

        msg_data = json.dumps({"type": "message", "data": message.to_dict()})

        try:
            await ws.send_text(msg_data)
        except Exception as e:
            print("[HUB] failed to send message to author", e)

        for other_ws in self.watchers.get(chunk_id, set()):
            if other_ws is ws:
                continue
            try:
                await other_ws.send_text(msg_data)
            except Exception as e:
                print("[HUB] failed to send message to peer", e)

    async def check_for_message(self, ws: WebSocket) -> None:
        if ws not in self.pos_by_ws:
            return

        chunk_id, row, col = self.pos_by_ws[ws]
        board = self._ensure_chunk(chunk_id)

        if get_bit(board[row, col], BIT_HAS_LINK):
            message = load_message(chunk_id, row, col)
            if message:
                try:
                    await ws.send_text(json.dumps({"type": "message", "data": message}))
                except Exception as e:
                    print("[HUB] failed to send existing message", e)
