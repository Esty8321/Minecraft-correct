import os, json, traceback
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from .settings import W, H
from .hub import Hub
from .db import clear_player_bits_all

JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "CHANGE_ME_123456789")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

app = FastAPI(title="-Voxel Server-")
hub = Hub()

@app.on_event("startup")
async def startup_event():
    clear_player_bits_all()

@app.on_event("shutdown")
async def shutdown_event():
    for ws in list(hub.pos_by_ws.keys()):
        try:
            await hub.disconnect(ws)
        except Exception as e:
            print('[MAIN] failed to disconnect', e)



@app.get("/")
def root():
    return {"ok": True, "w": W, "h": H}

def _extract_token(ws: WebSocket) -> str | None:
    # 1) query ?token=
    try:
        token = ws.query_params.get("token")
        if token:
            return token
    except:
        pass
    # 2) Authorization: Bearer ...
    try:
        auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            return auth[7:]
    except:
        pass
    return None

def _verify_token_or_reason(token: str | None) -> tuple[bool, str]:
    if not token:
        return False, "no token provided"
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        # אפשר גם לבדוק שדות כמו sub/iat וכו'
        return True, ""
    except JWTError as e:
        return False, f"invalid token: {e}"
    except Exception as e:
        return False, f"token error: {e}"

# @app.websocket("/ws")
# async def ws_endpoint(ws: WebSocket):
#     # 1) אמת טוקן לפני accept
#     token = _extract_token(ws)
#     ok, reason = _verify_token_or_reason(token)
#     if not ok:
#         try:
#             await ws.close(code=1008, reason=reason)  # Policy Violation
#         except:
#             pass
#         return

#     # 2) accept
#     try:
#         await ws.accept()
#     except Exception as e:
#         print("[ERROR] ws.accept failed:", e)
#         traceback.print_exc()
#         return

#     # 3) חבר ל-hub
#     try:
#         await hub.connect(ws)
#         print("[INFO] hub.connect succeeded for client:", ws.client)
#     except Exception as e:
#         print("[HUB][ERROR] connect failed:", e)
#         traceback.print_exc()
#         try:
#             await ws.close(code=1011, reason="hub.connect error")
#         except:
#             pass
#         return

#     # 4) לולאת הודעות
#     try:
#         while True:
#             try:
#                 msg = await ws.receive_text()
#             except WebSocketDisconnect as wd:
#                 print("[MAIN] WebSocketDisconnect received:", wd)
#                 break
#             except Exception as e:
#                 print("[MAIN] receive_text error:", e)
#                 traceback.print_exc()
#                 break

#             try:
#                 data = json.loads(msg)
#             except Exception as e:
#                 print("[MAIN] JSON parse error:", e, "raw:", msg)
#                 continue

#             k = (data.get("k") or "").lower()
#             try:
#                 if k in ("arrowup", "up"):
#                     await hub.move(ws, -1, 0)
#                 elif k in ("arrowdown", "down"):
#                     await hub.move(ws, +1, 0)
#                 elif k in ("arrowleft", "left"):
#                     await hub.move(ws, 0, -1)
#                 elif k in ("arrowright", "right"):
#                     await hub.move(ws, 0, +1)
#                 elif k in ("c", "color", "color++"):
#                     await hub.color_plus_plus(ws)
#                 elif k in ("whereami",):
#                     await hub._send_chunk(ws)
#                 else:
#                     print("[MAIN] unknown k:", k)
#             except Exception as e:
#                 print("[HUB][ERROR] action failed:", e)
#                 traceback.print_exc()
#                 try:
#                     await ws.send_text(json.dumps({"ok": False, "error": "action_failed", "msg": str(e)}))
#                 except:
#                     pass
#     finally:
#         # 5) ניתוק מסודר
#         print("[MAIN] connection closing, calling hub.disconnect")
#         try:
#             await hub.disconnect(ws)
#             print("[MAIN] hub.disconnect succeeded")
#         except Exception as e:
#             print("[MAIN] error during hub.disconnect:", e)
#             traceback.print_exc()
#         print("[MAIN] connection closed")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    token = _extract_token(ws)
    ok, reason = _verify_token_or_reason(token)
    if not ok:
        try:
            await ws.close(code=1008, reason=reason)  # Policy Violation
        except:
            pass
        return

    try:
        await ws.accept()
    except Exception as e:
        print("[ERROR] ws.accept failed:", e)
        traceback.print_exc()
        return

    try:
        await hub.connect(ws)
        print("[INFO] hub.connect succeeded for client:", ws.client)
        try:
            await hub.check_for_message(ws)
        except:
            pass
    except Exception as e:
        print("[HUB][ERROR] connect failed:", e)
        traceback.print_exc()
        try:
            await ws.close(code=1011, reason="hub.connect error")
        except:
            pass
        return

    try:
        while True:
            try:
                msg = await ws.receive_text()
            except WebSocketDisconnect as wd:
                print("[MAIN] WebSocketDisconnect received:", wd)
                break
            except Exception as e:
                print("[MAIN] receive_text error:", e)
                traceback.print_exc()
                break

            try:
                data = json.loads(msg)
            except Exception as e:
                print("[MAIN] JSON parse error:", e, "raw:", msg)
                continue

            k = (data.get("k") or "").lower()
            try:
                if k in ("arrowup", "up"):
                    await hub.move(ws, -1, 0)
                    await hub.check_for_message(ws)

                elif k in ("arrowdown", "down"):
                    await hub.move(ws, +1, 0)
                    await hub.check_for_message(ws)

                elif k in ("arrowleft", "left"):
                    await hub.move(ws, 0, -1)
                    await hub.check_for_message(ws)

                elif k in ("arrowright", "right"):
                    await hub.move(ws, 0, +1)
                    await hub.check_for_message(ws)

                elif k in ("c", "color", "color++"):
                    await hub.color_plus_plus(ws)

                elif k == "m":
                    content = (data.get("content") or "").strip()
                    if content:
                        await hub.write_message(ws, content)
                    else:
                        try:
                            await ws.send_text(json.dumps({
                                "ok": False, "type": "error",
                                "code": "EMPTY_MESSAGE",
                                "msg": "Message content is empty"
                            }))
                        except:
                            pass

                elif k in ("whereami",):
                    await hub._send_chunk(ws)

                else:
                    print("[MAIN] unknown k:", k)

            except Exception as e:
                print("[HUB][ERROR] action failed:", e)
                traceback.print_exc()
                try:
                    await ws.send_text(json.dumps({"ok": False, "error": "action_failed", "msg": str(e)}))
                except:
                    pass
    finally:
        print("[MAIN] connection closing, calling hub.disconnect")
        try:
            await hub.disconnect(ws)
            print("[MAIN] hub.disconnect succeeded")
        except Exception as e:
            print("[MAIN] error during hub.disconnect:", e)
            traceback.print_exc()
        print("[MAIN] connection closed")
