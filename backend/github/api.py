import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import GITHUB_TOKEN
from logs.logger import get_logger

logger = get_logger("github_api")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

BASE_URL = "https://api.github.com"

# Retry only on transient network failures (timeouts, connection drops) —
# NOT on 4xx/5xx responses, since those are handled explicitly below and
# retrying a bad-credentials or 404 response would just waste time.
_retry_on_network_error = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)),
    reraise=True,
)


@_retry_on_network_error
async def get_pr_diff(repo: str, pr_number: int) -> str:
    """PR ka actual code diff laao"""
    url = f"{BASE_URL}/repos/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers={**HEADERS, "Accept": "application/vnd.github.diff"})
        if response.status_code == 200:
            logger.info(f"Diff fetched for PR #{pr_number}")
            return response.text
        logger.error(f"Failed to fetch diff: {response.status_code}")
        return ""


@_retry_on_network_error
async def post_comment(repo: str, pr_number: int, comment: str) -> bool:
    """PR pe comment post karo"""
    url = f"{BASE_URL}/repos/{repo}/issues/{pr_number}/comments"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, headers=HEADERS, json={"body": comment})
        if response.status_code == 201:
            logger.info(f"Comment posted on PR #{pr_number} ✅")
            return True
        logger.error(f"Failed to post comment: {response.status_code}")
        return False


@_retry_on_network_error
async def merge_pr(repo: str, pr_number: int, commit_message: str) -> bool:
    """PR auto merge karo"""
    url = f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/merge"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.put(url, headers=HEADERS, json={
            "commit_title": f"MergeGuard Auto-Merge: PR #{pr_number}",
            "commit_message": commit_message,
            "merge_method": "squash"
        })
        if response.status_code == 200:
            logger.info(f"PR #{pr_number} auto-merged ✅")
            return True
        logger.error(f"Failed to merge PR: {response.status_code}")
        return False


@_retry_on_network_error
async def close_pr(repo: str, pr_number: int) -> bool:
    """PR reject karo (close karo)"""
    url = f"{BASE_URL}/repos/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.patch(url, headers=HEADERS, json={"state": "closed"})
        if response.status_code == 200:
            logger.info(f"PR #{pr_number} rejected and closed ❌")
            return True
        logger.error(f"Failed to close PR: {response.status_code}")
        return False
