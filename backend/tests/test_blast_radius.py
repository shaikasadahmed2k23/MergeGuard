import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.blast_radius as blast_radius


def test_low_risk_for_small_clean_diff():
    diff = "diff --git a/utils.py b/utils.py\n+def add(a, b):\n+    return a + b"
    result = blast_radius.calculate_blast_radius(diff, {"pr_number": 1})
    assert result["blast_radius"] == "low"


def test_high_risk_when_touching_auth_files():
    diff = "diff --git a/auth/login.py b/auth/login.py\n+def login(password):\n+    pass"
    result = blast_radius.calculate_blast_radius(diff, {"pr_number": 2})
    assert result["blast_radius"] == "high"
    assert any("sensitive" in r.lower() for r in result["reasons"])


def test_high_risk_for_database_migration():
    diff = "diff --git a/migrations/0001.sql b/migrations/0001.sql\n+CREATE TABLE users (id INT);"
    result = blast_radius.calculate_blast_radius(diff, {"pr_number": 3})
    assert result["blast_radius"] == "high"


def test_medium_risk_for_large_file_count():
    diff = "\n".join(
        f"diff --git a/file{i}.py b/file{i}.py\n+print({i})" for i in range(1, 7)
    )
    result = blast_radius.calculate_blast_radius(diff, {"pr_number": 4})
    assert result["blast_radius"] in ("medium", "high")
    assert result["files_changed"] == 6


def test_reports_no_risk_factors_message_when_clean():
    diff = "diff --git a/readme.md b/readme.md\n+Hello world"
    result = blast_radius.calculate_blast_radius(diff, {"pr_number": 5})
    assert result["reasons"] == ["No significant risk factors detected"]
