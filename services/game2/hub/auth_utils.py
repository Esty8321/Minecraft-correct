import os
import logging
from typing import Optional, Tuple
from fastapi import WebSocket
from jose import jwt, JWTError

logger = logging.getLogger(__name__)
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "CHANGE_ME_123456789")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

class AuthUtils:
    """JWT authentication utilities for verifying and extracting user tokens from WebSocket connections."""
    @staticmethod
    def extract_token(ws: WebSocket) -> Optional[str]:
        token = ws.query_params.get("token")
        if token:
            return token
        auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            return auth[7:]
        return None  

    @staticmethod
    def verify_token_or_reason(token: Optional[str]) -> Tuple[bool, str, Optional[str]]:
        if not token:
            return False, "no token provided", None
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
            user_id = str(payload.get("sub") or payload.get("id") or "")
            if not user_id:
                return False, "token missing sub/id", None
            return True, "", user_id
        except JWTError as e:
            return False, f"invalid token: {e}", None
        except Exception as e: 
            return False, f"token error: {e}", None
