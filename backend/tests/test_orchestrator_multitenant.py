import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.orchestrator as orchestrator


def _pr_data():
    return {
        "repo": "asad/demo-repo",
        "pr_number": 1,
        "author": "asad",
        "title": "Add feature",
        "description": "desc",
        "head_branch": "feature/x",
        "base_branch": "main",
        "pr_url": "https://github.com/asad/demo-repo/pull/1",
    }


@pytest.mark.asyncio
async def test_unregistered_repo_behaves_as_single_tenant(monkeypatch):
    # No repo_config found -> old single-tenant behavior, no BYOK key used
    async def fake_get_repo_config(repo):
        return None

    async def fake_get_pr_diff(repo, pr_number):
        return "diff --git a/x.py b/x.py"

    async def fake_build_file_context(*a, **kw):
        return "CODE DIFF:\n..."

    def fake_calculate_blast_radius(diff, pr_data):
        return {"blast_radius": "low", "reasons": [], "files_changed": 1}

    async def fake_get_developer_trust(repo, author):
        return {"adjustment": 0, "trust_level": "new", "note": "n/a"}

    captured = {}

    async def fake_adk_analyze_pr(pr_data, code_context):
        return {"results": {}, "trust_score": 90}

    async def fake_make_decision(pr_data, score, results, blast_radius, trust_profile, discord_override=None):
        captured["discord_override"] = discord_override
        captured["score"] = score

    class FakeKeyContext:
        def __init__(self, key):
            captured["custom_key_used"] = key

        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(orchestrator, "get_repo_config", fake_get_repo_config)
    monkeypatch.setattr(orchestrator, "get_pr_diff", fake_get_pr_diff)
    monkeypatch.setattr(orchestrator, "build_file_context", fake_build_file_context)
    monkeypatch.setattr(orchestrator, "calculate_blast_radius", fake_calculate_blast_radius)
    monkeypatch.setattr(orchestrator, "get_developer_trust", fake_get_developer_trust)
    monkeypatch.setattr(orchestrator, "adk_analyze_pr", fake_adk_analyze_pr)
    monkeypatch.setattr(orchestrator, "make_decision", fake_make_decision)
    monkeypatch.setattr(orchestrator, "use_gemini_key", FakeKeyContext)

    await orchestrator.run_pipeline(_pr_data())

    assert captured["custom_key_used"] is None
    assert captured["discord_override"] is None
    assert captured["score"] == 90


@pytest.mark.asyncio
async def test_registered_repo_with_byok_uses_custom_key(monkeypatch):
    async def fake_get_repo_config(repo):
        return {
            "discord_webhook_url": "https://discord.com/api/webhooks/custom",
            "api_key_encrypted": "encrypted-value",
            "trial_requests_used": 0,
        }

    async def fake_decrypt(value):
        return "user-own-gemini-key"

    async def fake_get_pr_diff(repo, pr_number):
        return "diff --git a/x.py b/x.py"

    async def fake_build_file_context(*a, **kw):
        return "CODE DIFF:\n..."

    def fake_calculate_blast_radius(diff, pr_data):
        return {"blast_radius": "low", "reasons": [], "files_changed": 1}

    async def fake_get_developer_trust(repo, author):
        return {"adjustment": 0, "trust_level": "new", "note": "n/a"}

    async def fake_adk_analyze_pr(pr_data, code_context):
        return {"results": {}, "trust_score": 80}

    captured = {}

    async def fake_make_decision(pr_data, score, results, blast_radius, trust_profile, discord_override=None):
        captured["discord_override"] = discord_override

    class FakeKeyContext:
        def __init__(self, key):
            captured["custom_key_used"] = key

        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(orchestrator, "get_repo_config", fake_get_repo_config)
    monkeypatch.setattr(orchestrator, "decrypt", lambda v: "user-own-gemini-key")
    monkeypatch.setattr(orchestrator, "get_pr_diff", fake_get_pr_diff)
    monkeypatch.setattr(orchestrator, "build_file_context", fake_build_file_context)
    monkeypatch.setattr(orchestrator, "calculate_blast_radius", fake_calculate_blast_radius)
    monkeypatch.setattr(orchestrator, "get_developer_trust", fake_get_developer_trust)
    monkeypatch.setattr(orchestrator, "adk_analyze_pr", fake_adk_analyze_pr)
    monkeypatch.setattr(orchestrator, "make_decision", fake_make_decision)
    monkeypatch.setattr(orchestrator, "use_gemini_key", FakeKeyContext)

    await orchestrator.run_pipeline(_pr_data())

    assert captured["custom_key_used"] == "user-own-gemini-key"
    assert captured["discord_override"] == "https://discord.com/api/webhooks/custom"


@pytest.mark.asyncio
async def test_trial_pool_exhausted_skips_pipeline_and_comments(monkeypatch):
    async def fake_get_repo_config(repo):
        return {
            "discord_webhook_url": None,
            "api_key_encrypted": None,
            "trial_requests_used": orchestrator.FREE_TRIAL_REQUESTS,
        }

    posted = {}

    async def fake_post_comment(repo, pr_number, comment):
        posted["comment"] = comment
        return True

    async def fake_get_pr_diff(*a, **kw):
        raise AssertionError("Should not reach diff-fetch when trial is exhausted")

    monkeypatch.setattr(orchestrator, "get_repo_config", fake_get_repo_config)
    monkeypatch.setattr(orchestrator, "post_comment", fake_post_comment)
    monkeypatch.setattr(orchestrator, "get_pr_diff", fake_get_pr_diff)

    await orchestrator.run_pipeline(_pr_data())

    assert "trial" in posted["comment"].lower()
