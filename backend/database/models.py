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

# ============================================
# MULTI-TENANT: users + repo_configs
# ============================================

async def upsert_user(github_id: int, github_username: str, access_token_encrypted: str) -> dict:
    """
    GitHub OAuth login ke baad user record banao ya update karo.
    Har login pe access token refresh ho jaata hai.
    """
    try:
        result = supabase.table("mergeguard_users").upsert(
            {
                "github_id": github_id,
                "github_username": github_username,
                "github_access_token_encrypted": access_token_encrypted,
            },
            on_conflict="github_id",
        ).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"upsert_user failed: {e}")
        return None


async def get_user_by_id(user_id: str) -> dict:
    """User record by internal UUID"""
    try:
        result = supabase.table("mergeguard_users").select("*").eq("id", user_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"get_user_by_id failed: {e}")
        return None


async def create_repo_config(user_id: str, repo_full_name: str, discord_webhook_url: str = None,
                              api_key_encrypted: str = None, github_webhook_id: int = None) -> dict:
    """
    Repo onboard karo — trial ya BYOK, dono ke liye same table.
    Upsert on repo_full_name: agar pehli baar partial fail hua tha (jaise
    webhook ban gaya but config save nahi hua), retry pe error nahi ayega —
    seedha update ho jayega.
    """
    try:
        result = supabase.table("repo_configs").upsert(
            {
                "user_id": user_id,
                "repo_full_name": repo_full_name,
                "discord_webhook_url": discord_webhook_url,
                "api_key_encrypted": api_key_encrypted,
                "github_webhook_id": github_webhook_id,
            },
            on_conflict="repo_full_name",
        ).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"create_repo_config failed: {e}")
        return None


async def get_repo_config(repo_full_name: str) -> dict:
    """
    Webhook aane par ye lookup hota hai — is repo ke liye koi multi-tenant
    config configured hai? Nahi mile toh caller purane single-tenant env
    vars pe fallback karega (backward-compatible, existing demo repo safe rehta hai).
    """
    try:
        result = supabase.table("repo_configs").select("*").eq("repo_full_name", repo_full_name).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"get_repo_config failed: {e}")
        return None


async def list_user_repo_configs(user_id: str) -> list:
    """Dashboard ke liye — is user ne kaunse repos onboard kiye hain"""
    try:
        result = supabase.table("repo_configs").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return result.data
    except Exception as e:
        logger.error(f"list_user_repo_configs failed: {e}")
        return []


async def increment_trial_usage(repo_full_name: str) -> None:
    """Trial pool use hone par counter badhao"""
    try:
        config = await get_repo_config(repo_full_name)
        if config:
            supabase.table("repo_configs").update(
                {"trial_requests_used": config.get("trial_requests_used", 0) + 1}
            ).eq("repo_full_name", repo_full_name).execute()
    except Exception as e:
        logger.error(f"increment_trial_usage failed: {e}")
