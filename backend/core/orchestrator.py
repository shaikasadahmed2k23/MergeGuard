from mergeguard_agent.runner_service import analyze_pr as adk_analyze_pr
from core.decision import make_decision
from core.blast_radius import calculate_blast_radius
from core.trust_profile import get_developer_trust
from github.api import get_pr_diff
from logs.logger import get_logger

logger = get_logger("orchestrator")

async def run_pipeline(pr_data: dict):
    repo = pr_data["repo"]
    pr_number = pr_data["pr_number"]
    author = pr_data["author"]

    logger.info(f"🚀 Pipeline started for PR #{pr_number} (ADK + Gemini)")

    # Step 1: Diff fetch karo
    diff = await get_pr_diff(repo, pr_number)
    if not diff:
        logger.error("Could not fetch diff — pipeline aborted")
        return

    # Step 2: Blast Radius calculate karo
    blast_radius = calculate_blast_radius(diff, pr_data)

    # Step 3: Developer Trust Profile nikalo (history se)
    trust_profile = await get_developer_trust(repo, author)

    # Step 4: ADK pipeline chalao
    logger.info("Running ADK multi-agent analysis...")
    adk_result = await adk_analyze_pr(pr_data, diff)

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
    await make_decision(pr_data, adjusted_score, all_results, blast_radius, trust_profile)