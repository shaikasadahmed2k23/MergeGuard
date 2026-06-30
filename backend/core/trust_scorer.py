from logs.logger import get_logger

logger = get_logger("trust_scorer")

# Har agent ka weight — security zyada important hai
WEIGHTS = {
    "security": 0.30,   # 30% — security issue = serious
    "diff":     0.25,   # 25% — actual code quality
    "intent":   0.20,   # 20% — kya banane wale ne jo bola wo kiya?
    "impact":   0.15,   # 15% — doosri cheezein toot to nahi?
    "context":  0.10,   # 10% — repo ke saath fit hai?
}

def calculate_score(results: dict) -> int:
    """
    Har agent ka score lo, weighted average nikalo.
    Final score = 0 to 100
    """
    total = 0.0

    for agent_name, weight in WEIGHTS.items():
        agent_result = results.get(agent_name, {})
        agent_score = agent_result.get("score", 50)  # default 50
        total += agent_score * weight
        logger.info(f"{agent_name}: {agent_score} × {weight} = {agent_score * weight:.1f}")

    final_score = round(total)
    logger.info(f"Final Trust Score: {final_score}/100")
    return final_score
