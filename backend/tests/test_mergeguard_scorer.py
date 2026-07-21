import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# This tests mergeguard_agent/scorer.py — the scorer actually used by the live
# ADK pipeline (core/trust_scorer.py with the same weights also exists in the
# codebase but is currently unused/dead code — see test_scorer.py).
import mergeguard_agent.scorer as live_scorer


def test_weighted_score_matches_expected_average():
    results = {
        "security": {"score": 100},
        "diff": {"score": 80},
        "intent": {"score": 60},
        "impact": {"score": 40},
        "context": {"score": 20},
    }
    result = live_scorer.calculate_trust_score(results)
    assert result["trust_score"] == 70


def test_security_critical_issue_forces_rejected_regardless_of_score():
    results = {
        "security": {"score": 95, "has_critical_issues": True},
        "diff": {"score": 100},
        "intent": {"score": 100},
        "impact": {"score": 100},
        "context": {"score": 100},
    }
    result = live_scorer.calculate_trust_score(results)
    assert result["decision"] == "rejected"


def test_high_score_without_critical_issues_is_approved():
    results = {agent: {"score": 95} for agent in ("security", "diff", "intent", "impact", "context")}
    result = live_scorer.calculate_trust_score(results)
    assert result["decision"] == "approved"


def test_mid_score_is_warned():
    results = {agent: {"score": 65} for agent in ("security", "diff", "intent", "impact", "context")}
    result = live_scorer.calculate_trust_score(results)
    assert result["decision"] == "warned"


def test_low_score_is_rejected():
    results = {agent: {"score": 20} for agent in ("security", "diff", "intent", "impact", "context")}
    result = live_scorer.calculate_trust_score(results)
    assert result["decision"] == "rejected"
