import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.trust_scorer as trust_scorer


def test_calculate_score_is_weighted_average_of_all_agents():
    results = {
        "security": {"score": 100},
        "diff": {"score": 80},
        "intent": {"score": 60},
        "impact": {"score": 40},
        "context": {"score": 20},
    }

    # 100*0.30 + 80*0.25 + 60*0.20 + 40*0.15 + 20*0.10 = 30+20+12+6+2 = 70
    assert trust_scorer.calculate_score(results) == 70


def test_calculate_score_defaults_missing_agent_to_fifty():
    # Only security reported — everything else should fall back to the 50 default
    results = {"security": {"score": 100}}

    # 100*0.30 + 50*0.25 + 50*0.20 + 50*0.15 + 50*0.10 = 30 + 35 = 65
    assert trust_scorer.calculate_score(results) == 65


def test_calculate_score_handles_completely_empty_results():
    # No agent results at all — every weight falls back to 50 -> final score is 50
    assert trust_scorer.calculate_score({}) == 50


def test_calculate_score_security_dominates_when_it_fails():
    # Security agent flags a critical issue (score 0) — even with perfect scores
    # elsewhere, the weighted average should drop noticeably because security
    # carries the highest weight (30%).
    results = {
        "security": {"score": 0},
        "diff": {"score": 100},
        "intent": {"score": 100},
        "impact": {"score": 100},
        "context": {"score": 100},
    }

    # 0*0.30 + 100*0.70 = 70
    assert trust_scorer.calculate_score(results) == 70


def test_calculate_score_always_returns_int_in_valid_range():
    results = {
        "security": {"score": 33},
        "diff": {"score": 67},
        "intent": {"score": 12},
        "impact": {"score": 89},
        "context": {"score": 45},
    }

    score = trust_scorer.calculate_score(results)
    assert isinstance(score, int)
    assert 0 <= score <= 100
