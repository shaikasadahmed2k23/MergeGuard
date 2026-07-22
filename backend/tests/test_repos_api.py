import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
import api.repos as repos_module
from middleware.jwt_auth import create_session_token

client = TestClient(app)


def _auth_header(user_id="user-123", username="asad"):
    token = create_session_token(user_id, username)
    return {"Authorization": f"Bearer {token}"}


def test_repos_requires_authentication():
    response = client.get("/api/repos")
    assert response.status_code == 401


def test_onboard_repo_creates_webhook_and_config(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return {"id": user_id, "github_access_token_encrypted": "encrypted-token"}

    async def fake_create_repo_webhook(user_access_token, repo, callback_url, webhook_secret):
        assert user_access_token == "decrypted-token"
        return {"success": True, "webhook_id": 999}

    async def fake_create_repo_config(**kwargs):
        return {"repo_full_name": kwargs["repo_full_name"]}

    monkeypatch.setattr(repos_module, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(repos_module, "decrypt", lambda v: "decrypted-token")
    monkeypatch.setattr(repos_module, "create_repo_webhook", fake_create_repo_webhook)
    monkeypatch.setattr(repos_module, "create_repo_config", fake_create_repo_config)

    response = client.post(
        "/api/repos",
        json={"repo_full_name": "asad/demo-repo", "discord_webhook_url": "https://discord.com/api/webhooks/x"},
        headers=_auth_header(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["repo_full_name"] == "asad/demo-repo"
    assert body["using_own_key"] is False
    assert body["trial_requests_remaining"] is not None


def test_onboard_repo_fails_gracefully_when_webhook_creation_fails(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return {"id": user_id, "github_access_token_encrypted": "encrypted-token"}

    async def fake_create_repo_webhook(user_access_token, repo, callback_url, webhook_secret):
        return {"success": False, "status_code": 404, "error": "Not Found"}

    monkeypatch.setattr(repos_module, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(repos_module, "decrypt", lambda v: "decrypted-token")
    monkeypatch.setattr(repos_module, "create_repo_webhook", fake_create_repo_webhook)

    response = client.post(
        "/api/repos",
        json={"repo_full_name": "asad/not-my-repo"},
        headers=_auth_header(),
    )

    assert response.status_code == 400


def test_list_my_repos_returns_only_this_users_repos(monkeypatch):
    async def fake_list_user_repo_configs(user_id):
        return [
            {
                "repo_full_name": "asad/demo-repo",
                "discord_webhook_url": None,
                "api_key_encrypted": None,
                "trial_requests_used": 2,
                "created_at": "2026-07-01T00:00:00Z",
            }
        ]

    monkeypatch.setattr(repos_module, "list_user_repo_configs", fake_list_user_repo_configs)

    response = client.get("/api/repos", headers=_auth_header())
    assert response.status_code == 200
    repos = response.json()["repos"]
    assert len(repos) == 1
    assert repos[0]["repo_full_name"] == "asad/demo-repo"
    assert repos[0]["trial_requests_remaining"] == repos_module.FREE_TRIAL_REQUESTS - 2


def test_get_reviews_blocked_for_repo_user_does_not_own(monkeypatch):
    async def fake_list_user_repo_configs(user_id):
        return [{"repo_full_name": "asad/some-other-repo"}]

    monkeypatch.setattr(repos_module, "list_user_repo_configs", fake_list_user_repo_configs)

    response = client.get("/api/repos/someone-else/private-repo/reviews", headers=_auth_header())
    assert response.status_code == 403
