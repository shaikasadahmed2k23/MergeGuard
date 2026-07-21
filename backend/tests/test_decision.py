import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.decision as decision


@pytest.mark.asyncio
async def test_make_decision_requires_human_review_for_high_blast_radius(monkeypatch):
    captured = {}

    async def fake_post_comment(repo, pr_number, comment):
        captured["comment"] = comment

    async def fake_save_pr_review(pr_data, score, results, review_state, blast_radius, trust_profile):
        captured["review_state"] = review_state

    async def fake_merge_pr(repo, pr_number, message):
        captured["merge"] = (repo, pr_number, message)

    async def fake_close_pr(repo, pr_number):
        captured["close"] = (repo, pr_number)

    monkeypatch.setattr(decision, "post_comment", fake_post_comment)
    monkeypatch.setattr(decision, "save_pr_review", fake_save_pr_review)
    monkeypatch.setattr(decision, "merge_pr", fake_merge_pr)
    monkeypatch.setattr(decision, "close_pr", fake_close_pr)

    pr_data = {"repo": "octo/demo", "pr_number": 42}
    blast_radius = {
        "blast_radius": "high",
        "files_changed": 20,
        "reasons": ["touches auth flow", "many services impacted"],
    }

    await decision.make_decision(
        pr_data,
        95,
        {"security": {"has_critical_issues": False}},
        blast_radius,
        {"trust_level": "trusted", "note": "High-confidence developer"},
    )

    assert captured["review_state"] == "warned"
    assert "HUMAN REVIEW REQUIRED" in captured["comment"]
    assert "merge" not in captured
    assert "close" not in captured
