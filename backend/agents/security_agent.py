from groq import AsyncGroq
from config import GROQ_API_KEY
from logs.logger import get_logger
import json

logger = get_logger("security_agent")
client = AsyncGroq(api_key=GROQ_API_KEY)

# Ye patterns agent ke saath double-check karte hain
DANGEROUS_PATTERNS = [
    "password", "passwd", "secret", "api_key", "apikey",
    "token", "private_key", "aws_secret", "eval(", "exec(",
    "subprocess", "os.system", "DROP TABLE", "DELETE FROM"
]

def quick_pattern_scan(diff: str) -> list:
    """
    Groq se pehle ek quick local scan —
    obvious cheezein pakad lo instantly
    """
    found = []
    diff_lower = diff.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in diff_lower:
            found.append(pattern)
    return found

async def run(pr_data: dict, diff: str) -> dict:
    """
    Security Agent:
    1. Pehle local pattern scan karo (fast)
    2. Phir Groq se deep analysis karo (smart)
    3. Dono combine karo — final result do
    """
    logger.info(f"Security Agent analyzing PR #{pr_data['pr_number']}")

    # Step 1: Quick local scan
    suspicious_patterns = quick_pattern_scan(diff)
    if suspicious_patterns:
        logger.warning(f"Suspicious patterns found locally: {suspicious_patterns}")

    # Step 2: Groq se deep analysis
    prompt = f"""You are a senior security engineer reviewing a code diff for security vulnerabilities.

PR Title: {pr_data['title']}
PR Author: {pr_data['author']}

Suspicious patterns already detected locally: {suspicious_patterns if suspicious_patterns else 'none'}

CODE DIFF TO ANALYZE:
{diff[:4000]}

Carefully check for:
1. Hardcoded secrets, passwords, API keys, tokens
2. SQL injection vulnerabilities
3. Command injection (eval, exec, os.system, subprocess)
4. Sensitive data exposure in logs or responses
5. Insecure dependencies or imports
6. Authentication/authorization bypasses
7. Path traversal vulnerabilities

Respond ONLY in this exact JSON format, no extra text:
{{
  "has_critical_issues": true/false,
  "has_warnings": true/false,
  "critical_issues": ["list of critical security issues found, or empty list"],
  "warnings": ["list of warnings, or empty list"],
  "severity": "critical/high/medium/low/none",
  "score": <number 0-100>,
  "summary": "one line security summary"
}}

Scoring guide:
- Critical issue found (hardcoded secret, injection) → score 0-30
- High severity warnings → score 31-55
- Medium warnings → score 56-75
- Minor or no issues → score 76-100"""

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()

        # Clean response agar backticks hon
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())

        # Local scan findings bhi add karo
        if suspicious_patterns and not result.get("has_critical_issues"):
            result["warnings"] = result.get("warnings", []) + [
                f"Suspicious pattern detected: {p}" for p in suspicious_patterns
            ]
            result["has_warnings"] = True
            # Score thoda kam karo agar local scan ne kuch pakda
            result["score"] = min(result.get("score", 75), 65)

        logger.info(f"Security Agent score: {result.get('score')} | Severity: {result.get('severity')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Security Agent JSON parse error: {e}")
        return {
            "has_critical_issues": False,
            "has_warnings": True,
            "critical_issues": [],
            "warnings": ["Could not complete security analysis"],
            "severity": "medium",
            "score": 50,
            "summary": "Security analysis incomplete — manual review recommended"
        }
    except Exception as e:
        logger.error(f"Security Agent error: {e}")
        return {
            "has_critical_issues": False,
            "has_warnings": True,
            "critical_issues": [],
            "warnings": [str(e)],
            "severity": "medium",
            "score": 50,
            "summary": "Security agent failed — manual review required"
        }
