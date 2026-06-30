import httpx
from config import DISCORD_WEBHOOK_URL
from logs.logger import get_logger

logger = get_logger("discord")


async def send_discord_notification(pr_data: dict, score: int, decision: str, blast_radius: dict, trust_profile: dict):
    """
    Har PR decision ke baad Discord channel mein message bhejta hai.
    Important PRs (human_review, reject) zyada highlighted hote hain.
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured — skipping notification")
        return

    pr_title = pr_data.get("title", "Untitled PR")
    pr_author = pr_data.get("author", "unknown")
    pr_url = pr_data.get("pr_url", "")
    pr_number = pr_data.get("pr_number", "?")
    repo = pr_data.get("repo", "unknown")

    blast_level = blast_radius.get("blast_radius", "low")

    # Decision ke hisaab se format decide karo
    if decision == "human_review":
        color = 0xFF3D57  # red
        title = f"🔴 ACTION NEEDED: PR #{pr_number}"
        content = "@here Please review this PR manually."
    elif decision == "rejected":
        color = 0xFF3D57  # red
        title = f"❌ PR #{pr_number} Rejected"
        content = ""
    elif decision == "warned":
        color = 0xFFB300  # amber
        title = f"🚩 PR #{pr_number} Merged with Warnings"
        content = ""
    else:  # approved
        color = 0x00C853  # green
        title = f"✅ PR #{pr_number} Approved & Merged"
        content = ""

    embed = {
        "title": title,
        "description": f"**{pr_title}**\nby `{pr_author}` in `{repo}`",
        "color": color,
        "fields": [
            {"name": "Trust Score", "value": f"{score}/100", "inline": True},
            {"name": "Blast Radius", "value": blast_level.upper(), "inline": True},
            {"name": "Developer Trust", "value": trust_profile.get("trust_level", "unknown").upper(), "inline": True},
        ],
        "url": pr_url,
        "footer": {"text": "MergeGuard — Autonomous Code Review"},
    }

    payload = {
        "content": content,
        "embeds": [embed],
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code in (200, 204):
                logger.info(f"Discord notification sent for PR #{pr_number} ✅")
            else:
                logger.error(f"Discord notification failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Discord notification error: {e}")