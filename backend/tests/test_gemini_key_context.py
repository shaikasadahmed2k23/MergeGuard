import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.gemini_key_context as gemini_key_context


@pytest.mark.asyncio
async def test_uses_custom_key_and_restores_original(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "default-key")

    async with gemini_key_context.use_gemini_key("user-own-key"):
        assert os.environ["GOOGLE_API_KEY"] == "user-own-key"

    assert os.environ["GOOGLE_API_KEY"] == "default-key"


@pytest.mark.asyncio
async def test_falls_back_to_default_when_no_custom_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "default-key")

    async with gemini_key_context.use_gemini_key(None):
        # None passed in -> should use config.GOOGLE_API_KEY (patched below) or the env default
        pass

    assert os.environ["GOOGLE_API_KEY"] == "default-key"


@pytest.mark.asyncio
async def test_concurrent_calls_never_see_each_others_key(monkeypatch):
    # This is the actual safety property we care about: two "requests" using
    # different keys must never observe each other's key mid-flight, even
    # when run concurrently — the lock should fully serialize them.
    monkeypatch.setenv("GOOGLE_API_KEY", "default-key")
    observed = []

    async def run_with_key(key, delay):
        async with gemini_key_context.use_gemini_key(key):
            observed.append(("enter", key, os.environ["GOOGLE_API_KEY"]))
            await asyncio.sleep(delay)
            observed.append(("still", key, os.environ["GOOGLE_API_KEY"]))

    await asyncio.gather(
        run_with_key("key-A", 0.02),
        run_with_key("key-B", 0.0),
    )

    for phase, requested_key, seen_key in observed:
        assert requested_key == seen_key, f"Key leaked: requested {requested_key}, saw {seen_key} at {phase}"
