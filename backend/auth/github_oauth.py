import hashlib
import hmac
import time
import urllib.parse

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from config import (
    GITHUB_OAUTH_CLIENT_ID,
    GITHUB_OAUTH_CLIENT_SECRET,
    JWT_SECRET,
    FRONTEND_URL,
)
from core.encryption import encrypt
from database.models import upsert_user
from middleware.jwt_auth import create_session_token
from logs.logger import get_logger

logger = get_logger("github_oauth")
router = APIRouter()

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# We need 'repo' scope so we can create a webhook on repos the user chooses
# to onboard. read:user is enough to identify who's logging in.
OAUTH_SCOPES = "repo read:user"

STATE_TTL_SECONDS = 600  # 10 minutes — plenty for a login redirect round trip


def _sign_state() -> str:
    """
    Stateless CSRF protection — sign a timestamp with JWT_SECRET instead of
    storing state server-side (no session store needed for a single redirect).
    """
    timestamp = str(int(time.time()))
    signature = hmac.new(JWT_SECRET.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def _verify_state(state: str) -> bool:
    try:
        timestamp, signature = state.split(".", 1)
    except ValueError:
        return False

    expected = hmac.new(JWT_SECRET.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False

    return (int(time.time()) - int(timestamp)) <= STATE_TTL_SECONDS


@router.get("/github/login")
async def github_login():
    """Redirects the user to GitHub's OAuth consent screen."""
    if not GITHUB_OAUTH_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured on this server")

    params = {
        "client_id": GITHUB_OAUTH_CLIENT_ID,
        "scope": OAUTH_SCOPES,
        "state": _sign_state(),
    }
    url = f"{GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str, state: str):
    """GitHub redirects here after the user approves access."""
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_OAUTH_CLIENT_ID,
                "client_secret": GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
            },
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error(f"GitHub token exchange failed: {token_data}")
            raise HTTPException(status_code=400, detail="GitHub token exchange failed")

        user_response = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub user profile")

        github_user = user_response.json()

    user = await upsert_user(
        github_id=github_user["id"],
        github_username=github_user["login"],
        access_token_encrypted=encrypt(access_token),
    )
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create/update user record")

    session_token = create_session_token(user["id"], github_user["login"])
    logger.info(f"User logged in ✅ {github_user['login']}")

    redirect_url = f"{FRONTEND_URL}/dashboard?token={session_token}"
    return RedirectResponse(redirect_url)
