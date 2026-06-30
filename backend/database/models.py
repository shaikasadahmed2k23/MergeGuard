from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
from logs.logger import get_logger

logger = get_logger("database")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def save_pr_review(pr_data: dict, score: int, results: dict, decision: str, blast_radius: dict = None, trust_profile: dict = None):
    """PR review result Supabase mein save karo"""
    try:
        security = results.get("security", {})
        intent = results.get("intent", {})
        diff = results.get("diff", {})
        impact = results.get("impact", {})
        context = results.get("context", {})

        record = {
            "blast_radius_level": blast_radius["blast_radius"] if blast_radius else None,
            "blast_radius_reasons": blast_radius["reasons"] if blast_radius else [],
            "developer_trust_level": trust_profile["trust_level"] if trust_profile else None,
            "developer_trust_note": trust_profile["note"] if trust_profile else None,
            "repo": pr_data["repo"],
            "pr_number": pr_data["pr_number"],
            "pr_title": pr_data["title"],
            "pr_author": pr_data["author"],
            "pr_url": pr_data["pr_url"],
            "trust_score": score,
            "decision": decision,
            "security_score": security.get("score"),
            "security_severity": security.get("severity"),
            "security_issues": security.get("critical_issues", []),
            "intent_score": intent.get("score"),
            "intent_matches": intent.get("intent_matches_code"),
            "diff_score": diff.get("score"),
            "has_bugs": diff.get("has_bugs"),
            "impact_score": impact.get("score"),
            "risk_level": impact.get("risk_level"),
            "context_score": context.get("score"),
            "full_results": results,
        }

        supabase.table("pr_reviews").insert(record).execute()
        logger.info(f"PR #{pr_data['pr_number']} saved to database ✅")

    except Exception as e:
        logger.error(f"Database save failed: {e}")

async def get_all_reviews(repo: str = None):
    """Saare reviews fetch karo — optional repo filter"""
    try:
        query = supabase.table("pr_reviews").select("*").order("created_at", desc=True)
        if repo:
            query = query.eq("repo", repo)
        result = query.execute()
        return result.data
    except Exception as e:
        logger.error(f"Database fetch failed: {e}")
        return []

async def get_review_by_pr(repo: str, pr_number: int):
    """Ek specific PR ki detail fetch karo"""
    try:
        result = supabase.table("pr_reviews")\
            .select("*")\
            .eq("repo", repo)\
            .eq("pr_number", pr_number)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Database fetch failed: {e}")
        return None

async def get_stats(repo: str = None):
    """Dashboard ke liye stats"""
    try:
        reviews = await get_all_reviews(repo)
        if not reviews:
            return {}

        total = len(reviews)
        approved = len([r for r in reviews if r["decision"] == "approved"])
        warned = len([r for r in reviews if r["decision"] == "warned"])
        rejected = len([r for r in reviews if r["decision"] == "rejected"])
        avg_score = sum(r["trust_score"] for r in reviews) / total

        return {
            "total_prs": total,
            "approved": approved,
            "warned": warned,
            "rejected": rejected,
            "avg_trust_score": round(avg_score, 1),
            "approval_rate": round((approved / total) * 100, 1),
        }
    except Exception as e:
        logger.error(f"Stats fetch failed: {e}")
        return {}