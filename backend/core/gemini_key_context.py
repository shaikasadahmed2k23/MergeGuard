import asyncio
import os
from contextlib import asynccontextmanager

from config import GOOGLE_API_KEY
from logs.logger import get_logger

logger = get_logger("gemini_key_context")

# WHY THIS EXISTS:
# Google ADK reads the Gemini API key from the GOOGLE_API_KEY env var at call
# time — it isn't passed in per-request the way a normal SDK client would take
# api_key=. There's no clean per-request key injection without a deeper ADK
# client refactor (constructing a fresh genai.Client per call), so for BYOK we
# temporarily swap the env var for the duration of ONE PR's analysis and
# restore it after.
#
# Because GOOGLE_API_KEY is process-global, two PR analyses running truly
# concurrently could leak one user's key into another user's request. To
# prevent that, EVERY analysis (trial-pool or BYOK) goes through this same
# lock — not just BYOK ones — so only one PR is ever being analyzed by the
# ADK pipeline at a time, process-wide.
#
# Trade-off: this serializes PR analysis (no concurrent throughput). That's
# the right call at trial-product scale where correctness (never leaking a
# user's key) matters more than parallel throughput. Worth revisiting with a
# real per-request genai.Client if MergeGuard needs to handle many repos
# analyzing PRs at the same moment.
_gemini_key_lock = asyncio.Lock()


@asynccontextmanager
async def use_gemini_key(api_key: str = None):
    """
    api_key=None -> use the shared default GOOGLE_API_KEY (trial pool).
    api_key=<value> -> temporarily use this user's own key instead.
    """
    async with _gemini_key_lock:
        original = os.environ.get("GOOGLE_API_KEY")
        os.environ["GOOGLE_API_KEY"] = api_key or GOOGLE_API_KEY or ""
        try:
            yield
        finally:
            if original is not None:
                os.environ["GOOGLE_API_KEY"] = original
            else:
                os.environ.pop("GOOGLE_API_KEY", None)
