import json
from fastapi import APIRouter, Request, HTTPException, Depends
from middleware.auth import verify_github_signature
from core.orchestrator import run_pipeline
from logs.logger import get_logger

logger = get_logger("webhook")
router = APIRouter()

@router.post("/github")
async def github_webhook(request: Request):
    # Step 1: Signature verify karo
    body = await verify_github_signature(request)

    # Step 2: Event type kya hai?
    event = request.headers.get("X-GitHub-Event")
    payload = json.loads(body)

    logger.info(f"Event received: {event}")

    # ✅ YE ADD KARO — ping handle karo
    # if event == "ping":
    #     logger.info("GitHub ping received ✅")
    #     return {"message": "pong"}
    
    if event == "ping":
        logger.info("GitHub ping received ✅")
        return {"message": "pong"}

    # Step 3: Sirf PR events handle karo
    if event != "pull_request":
        return {"message": f"Event '{event}' ignored"}
    
    # ... baaki code same rehga

    action = payload.get("action")

    # Sirf jab PR open ya update ho
    if action not in ["opened", "synchronize"]:
        return {"message": f"PR action '{action}' ignored"}

    pr_data = {
        "pr_number": payload["pull_request"]["number"],
        "title": payload["pull_request"]["title"],
        "description": payload["pull_request"]["body"] or "",
        "author": payload["pull_request"]["user"]["login"],
        "repo": payload["repository"]["full_name"],
        "base_branch": payload["pull_request"]["base"]["ref"],
        "head_branch": payload["pull_request"]["head"]["ref"],
        "diff_url": payload["pull_request"]["diff_url"],
        "pr_url": payload["pull_request"]["html_url"],
    }

    logger.info(f"PR #{pr_data['pr_number']} received from {pr_data['author']}")

    # Step 4: Agent pipeline start karo
    await run_pipeline(pr_data)

    return {"message": "Pipeline started", "pr": pr_data["pr_number"]}
