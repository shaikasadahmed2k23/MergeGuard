from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from config import GITHUB_WEBHOOK_SECRET, BACKEND_URL, FREE_TRIAL_REQUESTS
from core.encryption import encrypt, decrypt
from database.models import (
    get_user_by_id,
    create_repo_config,
    list_user_repo_configs,
    get_all_reviews,
)
from github.api import create_repo_webhook
from middleware.jwt_auth import get_current_user_id
from logs.logger import get_logger

logger = get_logger("api_repos")
router = APIRouter()


class OnboardRepoRequest(BaseModel):
    repo_full_name: str = Field(..., description="e.g. 'octocat/hello-world'")
    discord_webhook_url: Optional[str] = None
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="If omitted, the repo uses the shared free-trial pool (capped requests)",
    )


@router.post("/repos")
async def onboard_repo(body: OnboardRepoRequest, user_id: str = Depends(get_current_user_id)):
    """
    Logged-in user apna repo add karta hai. Hum unke OAuth token se webhook
    bana dete hain — unhe khud GitHub jaake kuch set up nahi karna padta.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = decrypt(user["github_access_token_encrypted"])
    callback_url = f"{BACKEND_URL}/webhook/github"

    webhook_result = await create_repo_webhook(
        user_access_token=access_token,
        repo=body.repo_full_name,
        callback_url=callback_url,
        webhook_secret=GITHUB_WEBHOOK_SECRET,
    )
    if not webhook_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=f"Could not create webhook on {body.repo_full_name} "
                    f"(GitHub returned {webhook_result.get('status_code')}): {webhook_result.get('error')}",
        )

    api_key_encrypted = encrypt(body.gemini_api_key) if body.gemini_api_key else None

    config = await create_repo_config(
        user_id=user_id,
        repo_full_name=body.repo_full_name,
        discord_webhook_url=body.discord_webhook_url,
        api_key_encrypted=api_key_encrypted,
        github_webhook_id=webhook_result["webhook_id"],
    )
    if not config:
        raise HTTPException(status_code=500, detail="Webhook created but failed to save config — contact support")

    return {
        "repo_full_name": config["repo_full_name"],
        "using_own_key": body.gemini_api_key is not None,
        "trial_requests_remaining": None if body.gemini_api_key else FREE_TRIAL_REQUESTS,
    }


@router.get("/repos")
async def list_my_repos(user_id: str = Depends(get_current_user_id)):
    """Dashboard: is user ne kaunse repos onboard kiye hain"""
    configs = await list_user_repo_configs(user_id)
    return {
        "repos": [
            {
                "repo_full_name": c["repo_full_name"],
                "discord_webhook_url": c["discord_webhook_url"],
                "using_own_key": c["api_key_encrypted"] is not None,
                "trial_requests_used": c["trial_requests_used"],
                "trial_requests_remaining": (
                    None if c["api_key_encrypted"] else max(0, FREE_TRIAL_REQUESTS - c["trial_requests_used"])
                ),
                "created_at": c["created_at"],
            }
            for c in configs
        ]
    }


@router.get("/repos/{repo_owner}/{repo_name}/reviews")
async def get_my_repo_reviews(repo_owner: str, repo_name: str, user_id: str = Depends(get_current_user_id)):
    """Dashboard: is repo ke saare PR reviews (ownership check ke saath)"""
    repo_full_name = f"{repo_owner}/{repo_name}"
    configs = await list_user_repo_configs(user_id)
    if not any(c["repo_full_name"] == repo_full_name for c in configs):
        raise HTTPException(status_code=403, detail="You haven't onboarded this repo")

    reviews = await get_all_reviews(repo_full_name)
    return {"reviews": reviews}
