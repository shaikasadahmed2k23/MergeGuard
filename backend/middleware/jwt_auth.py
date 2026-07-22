import jwt
import time
from fastapi import Header, HTTPException
from config import JWT_SECRET
from logs.logger import get_logger

logger = get_logger("jwt_auth")

SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def create_session_token(user_id: str, github_username: str) -> str:
    payload = {
        "sub": user_id,
        "username": github_username,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def get_current_user_id(authorization: str = Header(default=None)) -> str:
    """
    FastAPI dependency — 'Authorization: Bearer <token>' header se user_id nikalta hai.
    Route mein use: `user_id: str = Depends(get_current_user_id)`
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — please log in again")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid session token: {e}")
        raise HTTPException(status_code=401, detail="Invalid session token")
