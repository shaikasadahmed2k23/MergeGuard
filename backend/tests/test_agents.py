import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# NOTE: backend/agents/*.py (Groq-based) is currently NOT used by the live
# pipeline — core/orchestrator.py calls mergeguard_agent/ (Google ADK +
# Gemini) instead. These tests still cover real, working code, but if
# agents/*.py is intentionally kept as a fallback/reference implementation,
# say so in the README; otherwise it's worth removing to avoid confusing
# reviewers about which pipeline is actually live.
import agents.diff_agent as diff_agent
import agents.security_agent as security_agent
import agents.intent_agent as intent_agent


def _fake_groq_response(payload: dict):
    """Builds a fake object matching the shape of Groq's chat completion response."""
    message = SimpleNamespace(content=json.dumps(payload))
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.mark.asyncio
async def test_diff_agent_returns_parsed_result_on_valid_json(monkeypatch):
    expected = {
        "has_bugs": False,
        "bug_details": "none",
        "code_quality": "good",
        "quality_details": "clean diff",
        "score": 90,
        "summary": "Looks solid",
    }

    async def fake_create(*args, **kwargs):
        return _fake_groq_response(expected)

    monkeypatch.setattr(diff_agent.client.chat.completions, "create", fake_create)

    pr_data = {"pr_number": 1, "title": "Add feature", "description": "Adds a feature"}
    result = await diff_agent.run(pr_data, "diff --git a/x.py b/x.py\n+print(1)")

    assert result == expected


@pytest.mark.asyncio
async def test_diff_agent_falls_back_gracefully_on_malformed_json(monkeypatch):
    async def fake_create(*args, **kwargs):
        message = SimpleNamespace(content="not valid json at all")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(diff_agent.client.chat.completions, "create", fake_create)

    pr_data = {"pr_number": 2, "title": "Broken", "description": "desc"}
    result = await diff_agent.run(pr_data, "some diff")

    # Should never raise — must degrade to a safe default instead
    assert result["score"] == 50
    assert result["has_bugs"] is False


def test_security_agent_quick_scan_detects_hardcoded_secret():
    diff = 'password = "hunter2"\napi_key = "sk-abc123"'
    found = security_agent.quick_pattern_scan(diff)

    assert "password" in found
    assert "api_key" in found


def test_security_agent_quick_scan_clean_diff_finds_nothing():
    diff = "def add(a, b):\n    return a + b"
    found = security_agent.quick_pattern_scan(diff)

    assert found == []


@pytest.mark.asyncio
async def test_security_agent_downgrades_score_when_local_scan_flags_pattern(monkeypatch):
    # Groq itself sees no critical issues, but our local pattern scan found a
    # hardcoded secret — the agent should still lower the score and add a warning.
    llm_result = {
        "has_critical_issues": False,
        "has_warnings": False,
        "critical_issues": [],
        "warnings": [],
        "severity": "none",
        "score": 90,
        "summary": "Looks fine",
    }

    async def fake_create(*args, **kwargs):
        return _fake_groq_response(llm_result)

    monkeypatch.setattr(security_agent.client.chat.completions, "create", fake_create)

    pr_data = {"pr_number": 3, "title": "Add config", "author": "asad"}
    diff = 'aws_secret = "AKIA_something_sensitive"'
    result = await security_agent.run(pr_data, diff)

    assert result["has_warnings"] is True
    assert result["score"] <= 65
    assert any("aws_secret" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_intent_agent_penalizes_missing_description(monkeypatch):
    # No description at all -> should short-circuit before ever calling Groq
    called = {"hit": False}

    async def fake_create(*args, **kwargs):
        called["hit"] = True
        return _fake_groq_response({"score": 100})

    monkeypatch.setattr(intent_agent.client.chat.completions, "create", fake_create)

    pr_data = {"pr_number": 4, "title": "No description PR", "description": "", "author": "asad"}
    result = await intent_agent.run(pr_data, "diff --git a/x.py b/x.py")

    assert called["hit"] is False
    assert result["score"] == 30
    assert result["intent_matches_code"] is False
