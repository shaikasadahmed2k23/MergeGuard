from github.api import post_comment, merge_pr, close_pr
from logs.logger import get_logger
from database.models import save_pr_review
from notifications.discord_notifier import send_discord_notification

logger = get_logger("decision")


def build_comment(pr_data: dict, score: int, results: dict, decision: str, blast_radius: dict, trust_profile: dict) -> str:
    """Build the PR review comment with score, security, blast-radius, and trust context."""
    repo = pr_data.get("repo", "unknown")
    pr_number = pr_data.get("pr_number", "unknown")

    summaries = "\n".join([
        f"- **{k.title()} Agent**: {v.get('summary', 'N/A')}"
        for k, v in results.items()
    ])

    security = results.get("security", {})
    security_issues = security.get("issues", []) or []
    if security.get("has_critical_issues"):
        security_section = "### 🔒 Security Status: **CRITICAL ISSUES FOUND**\n" + "\n".join(
            [f"- {issue}" for issue in security_issues] if security_issues else ["- Critical security issues detected."]
        )
    else:
        security_section = "### 🔒 Security Status: **OK**\n- No critical issues detected."

    score_line = f"**Trust Score:** {score}/100"

    br_icon = "🔴" if blast_radius.get("blast_radius") == "high" else "🟡" if blast_radius.get("blast_radius") == "medium" else "🟢"
    br_reasons = "\n".join([f"  - {r}" for r in blast_radius.get("reasons", [])])
    blast_radius_section = f"""### {br_icon} Blast Radius: **{blast_radius.get('blast_radius', 'low').upper()}**
**Files Changed:** {blast_radius.get('files_changed', 0)}
**Risk Factors:**
{br_reasons}"""

    trust_section = f"""### 👤 Developer Trust: **{trust_profile.get('trust_level', 'unknown').upper().replace('_', ' ')}**
{trust_profile.get('note', 'No trust note available.')}"""

    if decision == "approve":
        header = "## 🤖 MergeGuard: **APPROVED & MERGED** ✅"
        footer = "*This PR was automatically merged by MergeGuard.*"
    elif decision == "warn":
        header = "## 🤖 MergeGuard: **MERGED WITH WARNINGS** 🚩"
        footer = "*Merged but please address the warnings above in future PRs.*"
    elif decision == "human_review":
        header = "## 🤖 MergeGuard: **HUMAN REVIEW REQUIRED** 👤"
        footer = "*This PR touches sensitive/high-risk areas. MergeGuard does not auto-merge high blast-radius changes, regardless of trust score. Please review manually.*"
    else:
        header = "## 🤖 MergeGuard: **REJECTED** ❌"
        footer = "*Please fix the issues above and reopen this PR.*"

    return f"""{header}

{score_line}

### Agent Analysis:
{summaries}

---

{blast_radius_section}

---

{trust_section}

---

{security_section}

---

{footer}

**Repository:** {repo}
**PR:** #{pr_number}"""


async def make_decision(pr_data: dict, score: int, results: dict, blast_radius: dict, trust_profile: dict):
    """
    Score + Blast Radius dono ke basis pe decision.

    Risk-Bounded Autonomy:
    - HIGH blast radius -> kabhi bhi auto-merge nahi, chahe score kuch bhi ho
    - LOW/MEDIUM blast radius -> normal score-based logic
    """
    repo = pr_data["repo"]
    pr_number = pr_data["pr_number"]

    security = results.get("security", {})
    if security.get("has_critical_issues"):
        logger.warning(f"PR #{pr_number} → FORCE REJECTED due to critical security issue!")
        comment = build_comment(pr_data, score, results, "reject", blast_radius, trust_profile)
        await save_pr_review(pr_data, score, results, "rejected", blast_radius, trust_profile)
        await send_discord_notification(pr_data, score, "rejected", blast_radius, trust_profile)
        await post_comment(repo, pr_number, comment)
        await close_pr(repo, pr_number)
        return

    if blast_radius.get("blast_radius") == "high":
        logger.warning(f"PR #{pr_number} → HUMAN REVIEW REQUIRED (high blast radius, score was {score})")
        comment = build_comment(pr_data, score, results, "human_review", blast_radius, trust_profile)
        await save_pr_review(pr_data, score, results, "warned", blast_radius, trust_profile)
        await send_discord_notification(pr_data, score, "human_review", blast_radius, trust_profile)
        await post_comment(repo, pr_number, comment)
        return

    if score >= 85:
        logger.info(f"PR #{pr_number} → AUTO MERGE ✅ (Score: {score})")
        comment = build_comment(pr_data, score, results, "approve", blast_radius, trust_profile)
        await save_pr_review(pr_data, score, results, "approved", blast_radius, trust_profile)
        await send_discord_notification(pr_data, score, "approved", blast_radius, trust_profile)
        await post_comment(repo, pr_number, comment)
        await merge_pr(repo, pr_number, f"MergeGuard Auto-Merge — Trust Score: {score}/100")

    elif score >= 60:
        logger.info(f"PR #{pr_number} → MERGED WITH WARNING 🚩 (Score: {score})")
        comment = build_comment(pr_data, score, results, "warn", blast_radius, trust_profile)
        await save_pr_review(pr_data, score, results, "warned", blast_radius, trust_profile)
        await send_discord_notification(pr_data, score, "warned", blast_radius, trust_profile)
        await post_comment(repo, pr_number, comment)
        await merge_pr(repo, pr_number, f"MergeGuard Merge (with warnings) — Trust Score: {score}/100")

    else:
        logger.info(f"PR #{pr_number} → REJECTED ❌ (Score: {score})")
        comment = build_comment(pr_data, score, results, "reject", blast_radius, trust_profile)
        await save_pr_review(pr_data, score, results, "rejected", blast_radius, trust_profile)
        await send_discord_notification(pr_data, score, "rejected", blast_radius, trust_profile)
        await post_comment(repo, pr_number, comment)
        await close_pr(repo, pr_number)
