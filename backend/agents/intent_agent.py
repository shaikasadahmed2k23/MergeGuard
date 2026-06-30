from groq import AsyncGroq
from config import GROQ_API_KEY
from logs.logger import get_logger
import json

logger = get_logger("intent_agent")
client = AsyncGroq(api_key=GROQ_API_KEY)

async def run(pr_data: dict, diff: str) -> dict:
    """
    Intent Agent:
    Developer ne PR description mein jo likha
    aur actual code change jo kiya — dono match karte hain?

    Ye gap bahut important hai —
    "Fixed login bug" likhke kuch aur karna = red flag
    """
    logger.info(f"Intent Agent analyzing PR #{pr_data['pr_number']}")

    description = pr_data.get("description", "").strip()

    # Agar description hi nahi — penalize karo
    if not description:
        logger.warning(f"PR #{pr_data['pr_number']} has no description!")
        return {
            "intent_clear": False,
            "intent_matches_code": False,
            "mismatch_details": "No PR description provided",
            "score": 30,
            "summary": "No description — cannot verify intent vs implementation"
        }

    prompt = f"""You are an expert code reviewer analyzing whether a pull request's stated intent matches its actual implementation.

PR Title: {pr_data['title']}
PR Description: {description}
PR Author: {pr_data['author']}

ACTUAL CODE CHANGES (diff):
{diff[:4000]}

Your job:
1. Understand what the developer SAID they did (from title + description)
2. Understand what the developer ACTUALLY did (from the diff)
3. Check if these match

Look for:
- Does the code change align with the stated purpose?
- Are there unexpected changes unrelated to the stated intent?
- Is the scope of changes appropriate for what was described?
- Does the PR do MORE than described (hidden changes)?
- Does the PR do LESS than described (incomplete implementation)?

Respond ONLY in this exact JSON format, no extra text:
{{
  "intent_clear": true/false,
  "intent_matches_code": true/false,
  "stated_intent": "what developer said they did",
  "actual_implementation": "what the code actually does",
  "mismatch_details": "describe any mismatch or 'none'",
  "hidden_changes": true/false,
  "hidden_changes_detail": "describe hidden changes or 'none'",
  "score": <number 0-100>,
  "summary": "one line intent analysis summary"
}}

Scoring guide:
- Intent clearly matches code, nothing hidden → score 85-100
- Minor mismatch or incomplete → score 60-84
- Significant mismatch or hidden changes → score 30-59
- No description or completely wrong → score 0-29"""

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
        logger.info(f"Intent Agent score: {result.get('score')} | Match: {result.get('intent_matches_code')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Intent Agent JSON parse error: {e}")
        return {
            "intent_clear": False,
            "intent_matches_code": False,
            "mismatch_details": "Could not parse intent analysis",
            "score": 50,
            "summary": "Intent analysis incomplete"
        }
    except Exception as e:
        logger.error(f"Intent Agent error: {e}")
        return {
            "intent_clear": False,
            "intent_matches_code": False,
            "mismatch_details": str(e),
            "score": 50,
            "summary": "Intent agent failed"
        }
