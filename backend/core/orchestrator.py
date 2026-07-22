from mergeguard_agent.runner_service import analyze_pr as adk_analyze_pr
from core.decision import make_decision
from core.blast_radius import calculate_blast_radius
from core.trust_profile import get_developer_trust
from core.file_context import build_file_context
from core.gemini_key_context import use_gemini_key
from core.encryption import decrypt
from database.models import get_repo_config, increment_trial_usage
from github.api import get_pr_diff, post_comment
from config import FREE_TRIAL_REQUESTS
from logs.logger import get_logger

logger = get_logger("orchestrator")


async def run_pipeline(pr_data: dict):
    repo = pr_data["repo"]
    pr_number = pr_data["pr_number"]
    author = pr_data["author"]

    logger.info(f"🚀 Pipeline started for PR #{pr_number} (ADK + Gemini)")

    # Multi-tenant lookup: has this repo been onboarded through the new
    # login + BYOK flow? If not, repo_config is None and everything below
    # behaves exactly as before — single-tenant, global env vars. This
    # keeps the existing demo repo working untouched.
    repo_config = await get_repo_config(repo)
    custom_api_key = None
    discord_webhook_override = None

    if repo_config:
        discord_webhook_override = repo_config.get("discord_webhook_url")

        if repo_config.get("api_key_encrypted"):
            custom_api_key = decrypt(repo_config["api_key_encrypted"])
        else:
            used = repo_config.get("trial_requests_used", 0)
            if used >= FREE_TRIAL_REQUESTS:
                logger.warning(f"Trial limit reached for {repo} — skipping analysis")
                await post_comment(
                    repo, pr_number,
                    "🤖 **MergeGuard**: Free trial requests used up for this repo. "
                    "Add your own free Gemini API key in the MergeGuard dashboard to keep using it — "
                    "no cost, just a few seconds to set up."
                )
                return
            await increment_trial_usage(repo)

    # Step 1: Diff fetch karo
    diff = await get_pr_diff(repo, pr_number)
    if not diff:
        logger.error("Could not fetch diff — pipeline aborted")
        return

    # Step 1b: Diff ke saath full file content bhi fetch karo — agents ko
    # sirf changed lines nahi, poora relevant file dikhna chahiye
    code_context = await build_file_context(repo, pr_number, pr_data["head_branch"], diff)

    # Step 2: Blast Radius calculate karo
    blast_radius = calculate_blast_radius(diff, pr_data)

    # Step 3: Developer Trust Profile nikalo (history se)
    trust_profile = await get_developer_trust(repo, author)

    # Step 4: ADK pipeline chalao — key-swapped + locked for multi-tenant
    # safety (see core/gemini_key_context.py for why this needs a
    # process-wide lock rather than just per-BYOK-request)
    logger.info("Running ADK multi-agent analysis...")
    async with use_gemini_key(custom_api_key):
        adk_result = await adk_analyze_pr(pr_data, code_context)

    all_results = adk_result["results"]
    raw_score = adk_result["trust_score"]

    # Step 5: Trust profile adjustment apply karo (sirf LOW/MEDIUM blast radius pe matter karega)
    adjusted_score = max(0, min(100, raw_score + trust_profile["adjustment"]))

    logger.info(
        f"All agents completed ✅ | Raw Score: {raw_score}/100 | "
        f"Trust Adjustment: {trust_profile['adjustment']:+d} | "
        f"Final Score: {adjusted_score}/100 | Blast Radius: {blast_radius['blast_radius']} | "
        f"Developer: {author} ({trust_profile['trust_level']})"
    )

    # Step 6: Final decision
    await make_decision(pr_data, adjusted_score, all_results, blast_radius, trust_profile, discord_webhook_override)
