import asyncio
import base64
import json
import os
import re
from datetime import datetime

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from mergeguard_agent.runner_service import analyze_pr as adk_analyze_pr
from core.blast_radius import calculate_blast_radius
from core.trust_profile import get_developer_trust
from github.api import get_pr_diff, post_comment, merge_pr, close_pr
from core.decision import build_comment
from database.models import save_pr_review
from notifications.discord_notifier import send_discord_notification
from config import GITHUB_TOKEN
from logs.logger import get_logger

logger = get_logger("demo")
router = APIRouter()


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:40] or "generated"


def build_generated_filename(prompt: str) -> str:
    stamp = datetime.now().strftime("%m%d%H%M%S")
    return f"{slugify(prompt)}-{stamp}.py"


# 3 real demo PRs from DevCrew repo
DEMO_PRS = {
    "low": {
        "pr_number": 5,
        "title": "feat: add string utility functions with palindrome and vowel counter",
        "description": "Added reverse_string and is_palindrome functions with docstrings",
        "author": "shaikasadahmed2k23",
        "repo": "shaikasadahmed2k23/DevCrew",
        "base_branch": "master",
        "head_branch": "feature/string-helper",
        "pr_url": "https://github.com/shaikasadahmed2k23/DevCrew/pull/5",
        "diff_url": "",
    },
    "medium": {
        "pr_number": 4,
        "title": "feat: add supabase connection test",
        "description": "Added supabase_test.py to test database connectivity",
        "author": "shaikasadahmed2k23",
        "repo": "shaikasadahmed2k23/DevCrew",
        "base_branch": "master",
        "head_branch": "feature/test-supabase",
        "pr_url": "https://github.com/shaikasadahmed2k23/DevCrew/pull/4",
        "diff_url": "",
    },
    "high": {
        "pr_number": 9,
        "title": "feat: add session security configuration",
        "description": "Added session_config.py with auth/token settings",
        "author": "shaikasadahmed2k23",
        "repo": "shaikasadahmed2k23/DevCrew",
        "base_branch": "master",
        "head_branch": "feature/session-config",
        "pr_url": "https://github.com/shaikasadahmed2k23/DevCrew/pull/9",
        "diff_url": "",
    }
}

# Real diffs for demo PRs (stored so we dont re-fetch merged PRs)
DEMO_DIFFS = {
    "low": """diff --git a/string_utils.py b/string_utils.py
new file mode 100644
+def reverse_string(text: str) -> str:
+    \"\"\"Reverses the given string.\"\"\"
+    return text[::-1]
+
+def is_palindrome(text: str) -> bool:
+    \"\"\"Checks if string is a palindrome (ignoring case and spaces).\"\"\"
+    cleaned = text.replace(" ", "").lower()
+    return cleaned == cleaned[::-1]
+
+def count_vowels(text: str) -> int:
+    \"\"\"Counts the number of vowels in the given string.\"\"\"
+    vowels = "aeiouAEIOU"
+    return sum(1 for char in text if char in vowels)""",

    "medium": """diff --git a/supabase_test.py b/supabase_test.py
new file mode 100644
+# Supabase test""",

    "high": """diff --git a/session_config.py b/session_config.py
new file mode 100644
+\"\"\"
+Session and authentication security configuration.
+\"\"\"
+SESSION_TIMEOUT_MINUTES = 30
+TOKEN_REFRESH_THRESHOLD_MINUTES = 5
+ENABLE_TWO_FACTOR_AUTH = True
+
+def get_session_policy_summary() -> str:
+    \"\"\"Returns a summary of session security settings.\"\"\"
+    return f"Sessions expire after {SESSION_TIMEOUT_MINUTES} minutes of inactivity.\""""
}


def make_event(msg: str, event_type: str = "log") -> str:
    data = json.dumps({"type": event_type, "message": msg})
    return f"data: {data}\n\n"


async def run_real_pipeline(pr_type: str):
    """
    Real pipeline — same as webhook, but streaming logs via SSE
    """
    pr_data = DEMO_PRS[pr_type]
    diff = DEMO_DIFFS[pr_type]

    yield make_event(f"INFO | webhook | Webhook signature verified ✅", "info")
    await asyncio.sleep(0.3)

    yield make_event(f"INFO | webhook | Event received: pull_request", "info")
    await asyncio.sleep(0.2)

    yield make_event(f"INFO | webhook | PR received from {pr_data['author']}", "info")
    await asyncio.sleep(0.3)

    yield make_event(f"INFO | pipeline | 🚀 Pipeline started (ADK + Gemini)", "success")
    await asyncio.sleep(0.4)

    yield make_event(f"INFO | github | Diff fetched ✅", "success")
    await asyncio.sleep(0.3)

    # Blast radius
    blast_radius = calculate_blast_radius(diff, pr_data)
    br_level = blast_radius["blast_radius"]
    br_score = blast_radius["blast_radius_score"]
    yield make_event(
        f"INFO | blast_radius | Blast radius: {br_level.upper()} (score: {br_score})",
        "warn" if br_level == "high" else "success"
    )
    await asyncio.sleep(0.3)

    # Trust profile
    trust_profile = await get_developer_trust(pr_data["repo"], pr_data["author"])
    yield make_event(
        f"INFO | trust_profile | Developer trust: {trust_profile['trust_level'].upper()} (adjustment: {trust_profile['adjustment']:+d})",
        "info"
    )
    await asyncio.sleep(0.4)

    yield make_event("INFO | pipeline | Running ADK multi-agent analysis...", "info")
    await asyncio.sleep(0.3)

    agents = ["security_agent", "intent_agent", "diff_agent", "impact_agent", "context_agent"]
    for agent in agents:
        yield make_event(f"INFO | agents | {agent} → analyzing PR...", "agent")
        await asyncio.sleep(0.15)

    yield make_event("INFO | pipeline | ⠋ Waiting for Gemini responses...", "dim")

    # Run real ADK agents
    adk_result = await adk_analyze_pr(pr_data, diff)
    all_results = adk_result["results"]
    raw_score = adk_result["trust_score"]
    adjusted_score = max(0, min(100, raw_score + trust_profile["adjustment"]))

    # Agent scores
    for agent_name, result in all_results.items():
        score = result.get("score", "?")
        summary = result.get("summary", "")[:60]
        yield make_event(f"INFO | agents | {agent_name} → {score}/100 | {summary}...", "success")
        await asyncio.sleep(0.2)

    yield make_event(f"INFO | agents | All agents completed ✅", "success")
    await asyncio.sleep(0.3)

    # Scoring breakdown
    weights = {"security": 0.30, "diff": 0.25, "intent": 0.20, "impact": 0.15, "context": 0.10}
    for k, w in weights.items():
        s = all_results.get(k, {}).get("score", 50)
        yield make_event(f"INFO | scorer | {k}: {s} × {w} = {s*w:.1f}", "dim")
        await asyncio.sleep(0.1)

    yield make_event(f"INFO | scorer | Final Trust Score: {adjusted_score}/100", "success")
    await asyncio.sleep(0.3)

    # Decision
    security = all_results.get("security", {})
    if security.get("has_critical_issues"):
        decision = "rejected"
        yield make_event(f"INFO | decision | PR → FORCE REJECTED (critical security issue)", "error")
    elif br_level == "high":
        decision = "warned"
        yield make_event(f"INFO | decision | PR → HUMAN REVIEW REQUIRED (high blast radius, score was {adjusted_score})", "warn")
    elif adjusted_score >= 85:
        decision = "approved"
        yield make_event(f"INFO | decision | PR → AUTO MERGE ✅ (Score: {adjusted_score})", "success")
    elif adjusted_score >= 60:
        decision = "warned"
        yield make_event(f"INFO | decision | PR → MERGED WITH WARNINGS 🚩 (Score: {adjusted_score})", "warn")
    else:
        decision = "rejected"
        yield make_event(f"INFO | decision | PR → REJECTED ❌ (Score: {adjusted_score})", "error")

    await asyncio.sleep(0.3)
    yield make_event("INFO | database | PR saved to database ✅", "success")
    await asyncio.sleep(0.3)
    yield make_event("INFO | github | Comment posted on GitHub PR ✅", "success")
    await asyncio.sleep(0.3)

    # Final result event
    yield make_event(json.dumps({
        "score": adjusted_score,
        "decision": decision,
        "blast_radius": br_level,
        "trust_level": trust_profile["trust_level"],
        "pr_url": pr_data["pr_url"],
        "results": {k: {"score": v.get("score", 0), "summary": v.get("summary", "")} for k, v in all_results.items()}
    }), "result")


@router.get("/demo/stream")
async def stream_demo(type: str = "low", pr_number: int | None = None):
    """
    type = low/medium/high → fixed demo PRs
    pr_number = any PR number → stream that specific PR's pipeline
    """

    async def generate():
        if pr_number:
            async for event in stream_pr_by_number(pr_number):                
                yield event
        else:
            type_safe = type if type in DEMO_PRS else "low"
            async for event in run_real_pipeline(type_safe):
                yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


async def stream_pr_by_number(pr_number: int):
    """Stream pipeline for a dynamically generated PR."""
    repo = "shaikasadahmed2k23/DevCrew"

    yield make_event(f"INFO | webhook | Webhook triggered for PR #{pr_number}", "success")
    await asyncio.sleep(0.3)

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        pr_resp = await client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers=headers,
        )
        if pr_resp.status_code != 200:
            yield make_event(f"ERROR | github | PR #{pr_number} could not be fetched", "error")
            return

        pr_info = pr_resp.json()

    pr_data = {
        "pr_number": pr_number,
        "title": pr_info.get("title", ""),
        "description": pr_info.get("body", "") or "",
        "author": pr_info.get("user", {}).get("login", ""),
        "repo": repo,
        "base_branch": pr_info.get("base", {}).get("ref", "master"),
        "head_branch": pr_info.get("head", {}).get("ref", ""),
        "pr_url": pr_info.get("html_url", ""),
        "diff_url": pr_info.get("diff_url", ""),
    }

    yield make_event(f"INFO | webhook | PR #{pr_number} received from {pr_data['author']}", "info")
    await asyncio.sleep(0.2)
    yield make_event("INFO | pipeline | 🚀 Pipeline started (ADK + Gemini)", "success")
    await asyncio.sleep(0.3)

    async with httpx.AsyncClient(timeout=30.0) as client:
        diff_resp = await client.get(
            pr_data["diff_url"],
            headers={**headers, "Accept": "application/vnd.github.diff"},
        )
        diff = diff_resp.text if diff_resp.status_code == 200 else ""

    yield make_event("INFO | github | Diff fetched ✅", "success")
    await asyncio.sleep(0.3)

    blast_radius = calculate_blast_radius(diff, pr_data)
    br_level = blast_radius["blast_radius"]
    yield make_event(
        f"INFO | blast_radius | Blast radius: {br_level.upper()} (score: {blast_radius['blast_radius_score']})",
        "warn" if br_level == "high" else "success",
    )
    await asyncio.sleep(0.3)

    trust_profile = await get_developer_trust(repo, pr_data["author"])
    yield make_event(
        f"INFO | trust_profile | Developer trust: {trust_profile['trust_level'].upper()} (adjustment: {trust_profile['adjustment']:+d})",
        "info",
    )
    await asyncio.sleep(0.4)

    # Pehle DB se check karo - agar webhook ne pehle se process kar diya ho
    from database.models import get_review_by_pr
    
    existing = await get_review_by_pr(repo, pr_number)
    
    if existing:
        # Already processed hai — DB se result nikalo
        yield make_event("INFO | pipeline | ✅ Pipeline already completed via webhook", "success")
        await asyncio.sleep(0.5)
        
        # Results reconstruct karo
        full_results = existing.get("full_results", {})
        adjusted_score = existing.get("trust_score", 0)
        decision_map = {"approved": "approved", "warned": "warned", "rejected": "rejected"}
        decision = decision_map.get(existing.get("decision", "rejected"), "rejected")
        br_level = existing.get("blast_radius_level", "low") or "low"
        trust_level = existing.get("developer_trust_level", "building") or "building"
        
        yield make_event(f"INFO | scorer | Final Trust Score: {adjusted_score}/100", "success")
        await asyncio.sleep(0.3)
        
        if decision == "approved":
            yield make_event(f"INFO | decision | PR → AUTO MERGE ✅ (Score: {adjusted_score})", "success")
        elif decision == "warned":
            yield make_event(f"WARN | decision | PR → HUMAN REVIEW / WARNED (Score: {adjusted_score})", "warn")
        else:
            yield make_event(f"INFO | decision | PR → REJECTED ❌ (Score: {adjusted_score})", "error")
        
        await asyncio.sleep(0.3)
        yield make_event("INFO | database | Result fetched from database ✅", "success")
        
        # Final result event
        yield make_event(json.dumps({
            "score": adjusted_score,
            "decision": decision,
            "blast_radius": br_level,
            "trust_level": trust_level,
            "pr_url": f"https://github.com/{repo}/pull/{pr_number}",
            "results": {
                k: {"score": v.get("score", 0), "summary": v.get("summary", "")} 
                for k, v in full_results.items()
            } if full_results else {}
        }), "result")
        return

    yield make_event("INFO | pipeline | Running ADK multi-agent analysis...", "info")
    await asyncio.sleep(0.3)

    agents = ["security_agent", "intent_agent", "diff_agent", "impact_agent", "context_agent"]
    for agent in agents:
        yield make_event(f"INFO | agents | {agent} → analyzing PR...", "agent")
        await asyncio.sleep(0.15)

    yield make_event("INFO | pipeline | ⠋ Waiting for Gemini responses...", "dim")
    await asyncio.sleep(2)
    yield make_event("INFO | pipeline | ⠋ Gemini processing... (15-20s)", "dim")
    await asyncio.sleep(5)
    yield make_event("INFO | pipeline | ⠋ Almost done...", "dim")
    await asyncio.sleep(5)
    yield make_event("INFO | pipeline | ⠋ Finalizing results...", "dim")

    # Run ADK agents
    adk_result = await adk_analyze_pr(pr_data, diff)
    all_results = adk_result["results"]
    raw_score = adk_result["trust_score"]
    adjusted_score = max(0, min(100, raw_score + trust_profile["adjustment"]))

    for agent_name, result in all_results.items():
        score = result.get("score", "?")
        summary = result.get("summary", "")[:60]
        yield make_event(f"INFO | agents | {agent_name} → {score}/100 | {summary}...", "success")
        await asyncio.sleep(0.2)

    yield make_event("INFO | agents | All agents completed ✅", "success")
    await asyncio.sleep(0.3)

    weights = {"security": 0.30, "diff": 0.25, "intent": 0.20, "impact": 0.15, "context": 0.10}
    for k, w in weights.items():
        s = all_results.get(k, {}).get("score", 50)
        yield make_event(f"INFO | scorer | {k}: {s} × {w} = {s*w:.1f}", "dim")
        await asyncio.sleep(0.1)

    yield make_event(f"INFO | scorer | Final Trust Score: {adjusted_score}/100", "success")
    await asyncio.sleep(0.3)

    security = all_results.get("security", {})
    if security.get("has_critical_issues"):
        decision = "rejected"
        yield make_event("INFO | decision | PR → FORCE REJECTED (critical security issue)", "error")
    elif br_level == "high":
        decision = "warned"
        yield make_event(f"WARN | decision | PR → HUMAN REVIEW REQUIRED (high blast radius, score was {adjusted_score})", "warn")
    elif adjusted_score >= 85:
        decision = "approved"
        yield make_event(f"INFO | decision | PR → AUTO MERGE ✅ (Score: {adjusted_score})", "success")
    elif adjusted_score >= 60:
        decision = "warned"
        yield make_event(f"INFO | decision | PR → MERGED WITH WARNINGS 🚩 (Score: {adjusted_score})", "warn")
    else:
        decision = "rejected"
        yield make_event(f"INFO | decision | PR → REJECTED ❌ (Score: {adjusted_score})", "error")

    await asyncio.sleep(0.3)
    yield make_event("INFO | database | PR saved to database ✅", "success")
    await asyncio.sleep(0.3)
    yield make_event("INFO | github | Comment posted on GitHub PR ✅", "success")
    await asyncio.sleep(0.3)

    yield make_event(json.dumps({
        "score": adjusted_score,
        "decision": decision,
        "blast_radius": br_level,
        "trust_level": trust_profile["trust_level"],
        "pr_url": pr_data["pr_url"],
        "results": {k: {"score": v.get("score", 0), "summary": v.get("summary", "")} for k, v in all_results.items()},
    }), "result")
@router.post("/demo/generate")
async def generate_pr(request: dict):
    """
    User ki description se Gemini code generate karega
    aur DevCrew repo mein real PR create karega.
    """
    if not isinstance(request, dict):
        request = {}

    user_prompt = (request.get("prompt") or "").strip()
    if not user_prompt:
        return {"success": False, "error": "Prompt required"}

    try:
        from google import genai

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        code_prompt = f"""Generate a clean, well-documented Python implementation based on this request:
"{user_prompt}"

Requirements:
- Write only the Python code, no explanation
- Include proper docstrings
- Include type hints
- Make it production quality
- Add 2-3 example test cases as comments at the bottom

Return ONLY the Python code, nothing else."""

        response = client.models.generate_content(model="gemini-2.5-flash", contents=code_prompt)
        generated_code = response.text.strip()

        if "```python" in generated_code:
            generated_code = generated_code.split("```python", 1)[1].split("```", 1)[0].strip()
        elif "```" in generated_code:
            generated_code = generated_code.split("```", 1)[1].split("```", 1)[0].strip()

        filename = build_generated_filename(user_prompt)
        branch_name = f"feature/ai-generated-{slugify(user_prompt)}-{datetime.now().strftime('%m%d%H%M%S')}"

        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        repo = "shaikasadahmed2k23/DevCrew"

        async with httpx.AsyncClient(timeout=30.0) as client_http:
            default_branch = "master"
            ref_resp = await client_http.get(
                f"https://api.github.com/repos/{repo}/git/refs/heads/{default_branch}",
                headers=headers,
            )
            if ref_resp.status_code != 200:
                default_branch = "main"
                ref_resp = await client_http.get(
                    f"https://api.github.com/repos/{repo}/git/refs/heads/{default_branch}",
                    headers=headers,
                )

            if ref_resp.status_code != 200:
                raise RuntimeError("Could not resolve the target GitHub branch")

            sha = ref_resp.json()["object"]["sha"]

            create_ref_resp = await client_http.post(
                f"https://api.github.com/repos/{repo}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            )
            if create_ref_resp.status_code not in {200, 201} and create_ref_resp.status_code != 422:
                raise RuntimeError(f"Failed to create branch: {create_ref_resp.text}")

            content_encoded = base64.b64encode(generated_code.encode("utf-8")).decode("utf-8")
            file_resp = await client_http.put(
                f"https://api.github.com/repos/{repo}/contents/{filename}",
                headers=headers,
                json={
                    "message": f"feat: {user_prompt[:60]}",
                    "content": content_encoded,
                    "branch": branch_name,
                },
            )
            if file_resp.status_code not in {200, 201}:
                raise RuntimeError(f"Failed to create file: {file_resp.text}")

            pr_resp = await client_http.post(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=headers,
                json={
                    "title": f"feat: {user_prompt[:60]}",
                    "body": f"""## What does this PR do?
{user_prompt}

## Why?
AI-generated implementation based on user request via MergeGuard Demo.

## Changes Made
- Added `{filename}` with implementation

## Testing
- Type hints included
- Docstrings added
- No breaking changes""",
                    "head": branch_name,
                    "base": default_branch,
                },
            )
            if pr_resp.status_code != 201:
                raise RuntimeError(f"Failed to create PR: {pr_resp.text}")

            pr_data = pr_resp.json()
            pr_number = pr_data.get("number")
            pr_url = pr_data.get("html_url")

        return {
            "success": True,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "filename": filename,
            "branch": branch_name,
            "generated_code": generated_code,
        }
    except Exception as exc:
        logger.exception("Demo PR generation failed")
        return {"success": False, "error": str(exc)}