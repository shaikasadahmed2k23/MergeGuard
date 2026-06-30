from database.models import get_all_reviews
from logs.logger import get_logger

logger = get_logger("trust_profile")


async def get_developer_trust(repo: str, author: str) -> dict:
    """
    Developer ka historical track record nikalo.
    Pichli PRs mein kitna accurate/trusted raha.
    """
    all_reviews = await get_all_reviews(repo)
    dev_reviews = [r for r in all_reviews if r.get("pr_author") == author]

    total = len(dev_reviews)

    if total == 0:
        return {
            "developer": author,
            "total_prs": 0,
            "trust_level": "new",
            "avg_score": None,
            "approval_rate": None,
            "adjustment": 0,
            "note": "First PR from this developer — no history yet, standard scrutiny applies.",
        }

    approved = len([r for r in dev_reviews if r["decision"] == "approved"])
    rejected = len([r for r in dev_reviews if r["decision"] == "rejected"])
    avg_score = sum(r["trust_score"] for r in dev_reviews) / total
    approval_rate = round((approved / total) * 100, 1)

    # Trust level classification
    if total >= 5 and approval_rate >= 80 and avg_score >= 80:
        trust_level = "trusted"
        adjustment = 5  # thoda benefit of doubt - score mein chhota boost
        note = f"Trusted developer — {approved}/{total} PRs approved historically (avg score {avg_score:.0f})."
    elif total >= 3 and (rejected / total) > 0.4:
        trust_level = "needs_scrutiny"
        adjustment = -5  # extra scrutiny - score thoda kam
        note = f"Elevated scrutiny — {rejected}/{total} PRs rejected historically."
    else:
        trust_level = "building"
        adjustment = 0
        note = f"Building track record — {total} PR(s) so far, avg score {avg_score:.0f}."

    logger.info(f"Trust profile for {author}: {trust_level} (adjustment: {adjustment:+d})")

    return {
        "developer": author,
        "total_prs": total,
        "trust_level": trust_level,
        "avg_score": round(avg_score, 1),
        "approval_rate": approval_rate,
        "adjustment": adjustment,
        "note": note,
    }