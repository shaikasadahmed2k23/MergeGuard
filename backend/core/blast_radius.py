import re
from logs.logger import get_logger

logger = get_logger("blast_radius")

# Files/patterns jo HIGH risk maane jaate hain
SENSITIVE_PATTERNS = [
    r"auth", r"login", r"password", r"payment", r"billing",
    r"security", r"token", r"secret", r"\.env", r"config",
    r"migration", r"schema", r"database", r"db\.py",
]

CRITICAL_FILE_EXTENSIONS = [".sql", ".env", "Dockerfile", "docker-compose"]


def calculate_blast_radius(diff: str, pr_data: dict) -> dict:
    """
    Diff dekh kar risk classify karta hai - LOW / MEDIUM / HIGH
    Ye deterministic logic hai, LLM nahi - fast aur explainable.
    """
    risk_score = 0
    reasons = []

    # 1. Kitni files affected hain
    file_headers = re.findall(r"diff --git a/(.*?) b/", diff)
    files_changed = len(set(file_headers)) if file_headers else 1

    if files_changed > 5:
        risk_score += 25
        reasons.append(f"{files_changed} files changed in a single PR (large scope)")
    elif files_changed > 2:
        risk_score += 10
        reasons.append(f"{files_changed} files changed (moderate scope)")

    # 2. Sensitive area check (auth, payment, security, etc.)
    diff_lower = diff.lower()
    matched_patterns = [p for p in SENSITIVE_PATTERNS if re.search(p, diff_lower)]
    if matched_patterns:
        risk_score += 40
        reasons.append(f"Touches sensitive area: {', '.join(matched_patterns[:3])}")

    # 3. Critical file types
    for ext in CRITICAL_FILE_EXTENSIONS:
        if ext in diff_lower:
            risk_score += 30
            reasons.append(f"Modifies critical file type: {ext}")
            break

    # 4. Database/schema changes
    if re.search(r"(create table|alter table|drop table|migration)", diff_lower):
        risk_score += 35
        reasons.append("Database schema change detected")

    # 5. Deletion heavy changes (could break things elsewhere)
    deletions = diff.count("\n-")
    additions = diff.count("\n+")
    if deletions > additions * 1.5 and deletions > 10:
        risk_score += 15
        reasons.append("PR removes significantly more code than it adds")

    # Classify
# Naya - sensitive pattern akela bhi high trigger kare
    if risk_score >= 40:
        level = "high"
    elif risk_score >= 15:
        level = "medium"
    else:
        level = "low"

    logger.info(f"Blast radius for PR #{pr_data['pr_number']}: {level} (score: {risk_score})")

    return {
        "blast_radius": level,
        "blast_radius_score": risk_score,
        "files_changed": files_changed,
        "reasons": reasons if reasons else ["No significant risk factors detected"],
    }