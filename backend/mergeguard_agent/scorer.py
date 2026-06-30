def calculate_trust_score(results: dict) -> dict:
    """
    5 agents ke results lo, weighted score nikaalo,
    decision lo (approve/warn/reject)
    """
    WEIGHTS = {
        "security": 0.30,
        "diff": 0.25,
        "intent": 0.20,
        "impact": 0.15,
        "context": 0.10,
    }

    total = 0.0
    for agent_name, weight in WEIGHTS.items():
        agent_result = results.get(agent_name, {})
        score = agent_result.get("score", 50)
        total += score * weight

    final_score = round(total)

    # Critical security override - chahe score kuch bhi ho
    security = results.get("security", {})
    if security.get("has_critical_issues"):
        decision = "rejected"
    elif final_score >= 85:
        decision = "approved"
    elif final_score >= 60:
        decision = "warned"
    else:
        decision = "rejected"

    return {
        "trust_score": final_score,
        "decision": decision,
    }