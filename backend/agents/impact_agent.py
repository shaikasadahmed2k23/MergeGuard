from groq import AsyncGroq
from config import GROQ_API_KEY
from logs.logger import get_logger
import json

logger = get_logger("impact_agent")
client = AsyncGroq(api_key=GROQ_API_KEY)

async def run(pr_data: dict, diff: str) -> dict:
    """
    Impact Agent:
    Ye change kisi aur cheez ko tod toh nahi raha?

    Check karta hai:
    - Breaking changes (function signatures change, API endpoints)
    - Missing imports ya dependencies
    - Deleted code jo kahin use ho raha ho
    - Database schema changes without migration
    - Environment variables added but not documented
    """
    logger.info(f"Impact Agent analyzing PR #{pr_data['pr_number']}")

    prompt = f"""You are a senior backend engineer analyzing the potential impact and side effects of a code change.

PR Title: {pr_data['title']}
PR Description: {pr_data.get('description', 'No description')}
Base Branch: {pr_data['base_branch']}

CODE DIFF:
{diff[:4000]}

Carefully analyze for:
1. Breaking changes — function/method signatures changed, API contracts broken
2. Missing imports — are new dependencies used but not imported?
3. Deleted code — is anything removed that might be used elsewhere?
4. Database changes — schema changes without migrations?
5. New environment variables — added but not documented in .env.example?
6. Dependency changes — new packages added, version conflicts?
7. Performance impact — any obvious performance regressions (N+1 queries, loops, etc.)?
8. Test coverage — are tests updated to cover the new changes?

Respond ONLY in this exact JSON format, no extra text:
{{
  "has_breaking_changes": true/false,
  "breaking_changes": ["list of breaking changes or empty list"],
  "missing_imports": true/false,
  "missing_imports_detail": "details or 'none'",
  "needs_migration": true/false,
  "undocumented_env_vars": ["list of new undocumented env vars or empty list"],
  "performance_concerns": true/false,
  "performance_details": "details or 'none'",
  "tests_updated": true/false,
  "risk_level": "high/medium/low",
  "score": <number 0-100>,
  "summary": "one line impact analysis summary"
}}

Scoring guide:
- No breaking changes, tests updated, clean → score 80-100
- Minor impact, low risk → score 60-79
- Breaking changes or missing tests → score 35-59
- High risk, breaking changes + no tests → score 0-34"""

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        logger.info(f"Impact Agent score: {result.get('score')} | Risk: {result.get('risk_level')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Impact Agent JSON parse error: {e}")
        return {
            "has_breaking_changes": False,
            "breaking_changes": [],
            "risk_level": "medium",
            "score": 50,
            "summary": "Impact analysis incomplete — manual review recommended"
        }
    except Exception as e:
        logger.error(f"Impact Agent error: {e}")
        return {
            "has_breaking_changes": False,
            "breaking_changes": [],
            "risk_level": "medium",
            "score": 50,
            "summary": "Impact agent failed"
        }
