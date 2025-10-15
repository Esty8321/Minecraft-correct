from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from jose import jwt
import os, json, time, re

app = FastAPI()

DATA = Path(__file__).parent / "users.json"
DATA.parent.mkdir(parents=True, exist_ok=True)
if not DATA.exists():
    DATA.write_text(json.dumps({"users": []}, ensure_ascii=False, indent=2), encoding="utf-8")

JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "CHANGE_ME_123456789")
JWT_ALG = "HS256"

BIN8_RE = re.compile(r"^[01]{8}$")

class RegisterIn(BaseModel):
    username: str
    email: EmailStr

class LoginIn(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    user_id: Optional[Union[int, str]] = None

def to_bin8(n: int) -> str:
    return f"{(n & 0xFF):08b}"

def normalize_users(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for u in users:
        uid = u.get("id")
        if isinstance(uid, int):
            u["id"] = to_bin8(uid)
        elif isinstance(uid, str) and BIN8_RE.fullmatch(uid):
            pass
        else:
            try:
                n = int(uid)
                u["id"] = to_bin8(n)
            except Exception:
                raise HTTPException(500, f"bad_user_id_format: {uid!r}")
    return users

def load_db() -> Dict[str, Any]:
    with open(DATA, "r", encoding="utf-8") as f:
        db = json.load(f)
    db["users"] = normalize_users(db.get("users", []))
    return db

def save_db(obj: Dict[str, Any]):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def next_free_id(users: List[Dict[str, Any]]) -> str:
    used_nums = set()
    for u in users:
        uid = u.get("id")
        if isinstance(uid, str) and BIN8_RE.fullmatch(uid):
            used_nums.add(int(uid, 2))
        elif isinstance(uid, int):
            used_nums.add(uid & 0xFF)
        else:
            raise HTTPException(500, "corrupted_user_id")
    for n in range(256):
        if n not in used_nums:
            return to_bin8(n)
    raise HTTPException(409, "id_space_exhausted_0_255")

@app.post("/register")
def register(inp: RegisterIn):
    db = load_db()
    users = db.get("users", [])
    if any(u["username"].lower() == inp.username.lower() for u in users):
        raise HTTPException(409, "username_taken")
    if any(u["email"].lower() == inp.email.lower() for u in users):
        raise HTTPException(409, "email_taken")

    uid = next_free_id(users)
    user = {"id": uid, "username": inp.username, "email": inp.email}
    users.append(user)
    db["users"] = users
    save_db(db)
    
    now = int(time.time())
    token = jwt.encode(
        {"sub": user["id"], "username": user["username"], "iat": now},  # ללא exp
        JWT_SECRET,
        algorithm=JWT_ALG,
    )
    #insert for the active users in the chat
    return {"ok": True, "user": user, "token": token,"player_id":user["id"]}

@app.post("/login")
def login(inp: LoginIn):
    print(f"[AUTH] /login called with: username={inp.username}, email={inp.email}, user_id={inp.user_id}")
    db = load_db()
    users = db.get("users", [])
    print(f"[AUTH] loaded {len(users)} users")

    user = None

    if inp.user_id is not None:
        print(f"[AUTH] searching by user_id={inp.user_id}")

        if isinstance(inp.user_id, int):
            wanted = to_bin8(inp.user_id)
        elif isinstance(inp.user_id, str):
            wanted = inp.user_id if BIN8_RE.fullmatch(inp.user_id) else to_bin8(int(inp.user_id))
        else:
            raise HTTPException(400, "bad_user_id_type")
        user = next((u for u in users if u["id"] == wanted), None)

    if not user and inp.username:
        print(f"[AUTH] searching by username={inp.username}")
        user = next((u for u in users if u["username"].lower() == inp.username.lower()), None)

    if not user and inp.email:
        print(f"[AUTH] searching by email={inp.email}")

        user = next((u for u in users if u["email"].lower() == inp.email.lower()), None)

    if not user:
        print("[AUTH] user not found ❌")
        raise HTTPException(401, "user_not_found")

    now = int(time.time())
    token = jwt.encode(
        {"sub": user["id"], "username": user["username"], "iat": now},  # ללא exp
        JWT_SECRET,
        algorithm=JWT_ALG,
    )
    print(f"[AUTH] ✅ success for {user['username']} id={user['id']}")
    #insert for the active users in the chat
    return {"ok": True, "user": user, "token": token, "player_id":user["id"]}

@app.get("/health")
def health():
    return {"ok": True, "service": "auth"}

@app.get("/players")
async def get_players():
    try:
        if not DATA.exists():
            print(f"[AUTH] users.json not found at {DATA}")
            return {"players": []}

        with open(DATA, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {"players": data.get("users", [])}
    except Exception as e:
        print(f"[AUTH] Error reading players:", e)
        return {"players": []}
