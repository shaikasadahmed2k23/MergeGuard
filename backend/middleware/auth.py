import hmac
import hashlib
from fastapi import Request, HTTPException
from config import GITHUB_WEBHOOK_SECRET
from logs.logger import get_logger

logger = get_logger("auth")

async def verify_github_signature(request: Request) -> bytes:
    """
    GitHub har webhook ke saath ek signature bhejta hai.
    Hum verify karte hain ki request genuine GitHub se aayi hai.
    Fake request aaye toh block kar do.
    """
    signature = request.headers.get("X-Hub-Signature-256")

    if not signature:
        logger.warning("Webhook signature missing - request rejected")
        raise HTTPException(status_code=401, detail="Signature missing")

    body = await request.body()

    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        logger.warning("Invalid webhook signature - possible fake request")
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info("Webhook signature verified ✅")
    return body
