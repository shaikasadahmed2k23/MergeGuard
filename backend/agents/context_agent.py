from groq import AsyncGroq
from config import GROQ_API_KEY
from logs.logger import get_logger
import json

logger = get_logger("context_agent")
client = AsyncGroq(api_key=GROQ_API_KEY)

async def run(pr_data: dict, diff: str) -> dict:
    """
    Context Agent:
    Ye change repo ke overall context mein fit baithta hai?

    Check karta hai:
    - Sahi folder structure follow kiya?
    - Naming conventions sahi hain?
    - Code style consistent hai baaki codebase se?
    - Branch name meaningful hai?
    """
    logger.info(f"Context Agent analyzing PR #{pr_data['pr_number']}")

    prompt = f"""You are a senior software architect reviewing a pull request for code consistency and project fit.

PR Title: {pr_data['title']}
PR Description: {pr_data.get('description', 'No description')}
PR Author: {pr_data['author']}
Base Branch: {pr_data['base_branch']}
Feature Branch: {pr_data['head_branch']}
Repository: {pr_data['repo']}

CODE DIFF:
{diff[:4000]}

Analyze the following:
1. Branch naming — is it meaningful and follows conventions? (feature/, fix/, hotfix/, test/, etc.)
2. Code style — does it look consistent with what you can infer about the codebase?
3. File placement — are files being modified/added in appropriate locations?
4. Commit message quality — does the PR title reflect a good commit message?
5. Scope — is this PR focused or does it touch too many unrelated things?
6. Documentation — are there comments where needed?

Respond ONLY in this exact JSON format, no extra text:
{{
  "branch_name_good": true/false,
  "code_style_consistent": true/false,
  "pr_focused": true/false,
  "has_documentation": true/false,
  "issues": ["list of context issues found, or empty list"],
  "positives": ["list of good things found"],
  "score": <number 0-100>,
  "summary": "one line context analysis summary"
}}

Scoring guide:
- Well structured, focused, good naming → score 80-100
- Minor issues with style or naming → score 60-79
- Unfocused PR touching many things → score 40-59
- Poor structure, no conventions followed → score 0-39"""

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
        logger.info(f"Context Agent score: {result.get('score')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Context Agent JSON parse error: {e}")
        return {
            "branch_name_good": False,
            "code_style_consistent": False,
            "pr_focused": False,
            "issues": ["Could not complete context analysis"],
            "score": 50,
            "summary": "Context analysis incomplete"
        }
    except Exception as e:
        logger.error(f"Context Agent error: {e}")
        return {
            "branch_name_good": False,
            "code_style_consistent": False,
            "issues": [str(e)],
            "score": 50,
            "summary": "Context agent failed"
        }
