import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import GITHUB_WEBHOOK_SECRET
import webhook.github as webhook_module
from main import app

client = TestClient(app)


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()


def test_webhook_rejects_missing_signature():
    body = json.dumps({"action": "opened"}).encode()
    response = client.post(
        "/webhook/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 401


def test_webhook_rejects_invalid_signature():
    body = json.dumps({"action": "opened"}).encode()
    response = client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert response.status_code == 401


def test_webhook_handles_ping_with_valid_signature():
    body = json.dumps({"zen": "Keep it logically awesome."}).encode()
    response = client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_webhook_ignores_non_pull_request_events():
    body = json.dumps({"action": "created"}).encode()
    response = client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert "ignored" in response.json()["message"]


def test_webhook_ignores_non_opened_or_synchronize_pr_actions():
    body = json.dumps({"action": "closed"}).encode()
    response = client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert "ignored" in response.json()["message"]


def test_webhook_triggers_pipeline_for_opened_pr(monkeypatch):
    captured = {}

    async def fake_run_pipeline(pr_data):
        captured["pr_data"] = pr_data

    monkeypatch.setattr(webhook_module, "run_pipeline", fake_run_pipeline)

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 7,
            "title": "Add retry logic",
            "body": "Wraps external calls with tenacity",
            "user": {"login": "asad"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/retries"},
            "diff_url": "https://github.com/x/y/pull/7.diff",
            "html_url": "https://github.com/x/y/pull/7",
        },
        "repository": {"full_name": "x/y"},
    }
    body = json.dumps(payload).encode()

    response = client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
    )

    assert response.status_code == 200
    assert captured["pr_data"]["pr_number"] == 7
    assert captured["pr_data"]["author"] == "asad"
    assert captured["pr_data"]["repo"] == "x/y"
