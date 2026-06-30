from groq import AsyncGroq
from config import GROQ_API_KEY
from logs.logger import get_logger

logger = get_logger("diff_agent")
client = AsyncGroq(api_key=GROQ_API_KEY)

async def run(pr_data: dict, diff: str) -> dict:
    """
    Diff Agent:
    Code ki actual changes dekhta hai.
    Bugs, logical errors, code quality check karta hai.
    """
    logger.info(f"Diff Agent analyzing PR #{pr_data['pr_number']}")

    prompt = f"""You are an expert code reviewer. Analyze the following code diff carefully.

PR Title: {pr_data['title']}
PR Description: {pr_data['description']}

CODE DIFF:
{diff[:4000]}

Analyze and respond in this exact JSON format:
{{
  "has_bugs": true/false,
  "bug_details": "describe any bugs found or 'none'",
  "code_quality": "good/moderate/poor",
  "quality_details": "explain the quality issues",
  "score": <number 0-100>,
  "summary": "one line summary of the diff analysis"
}}

Respond ONLY with the JSON. No extra text."""

    response = await client.chat.completions.create(
        # model="llama3-70b-8192",
        model="llama-3.3-70b-versatile",

        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    import json
    try:
        result = json.loads(response.choices[0].message.content)
        logger.info(f"Diff Agent score: {result.get('score')}")
        return result
    except Exception as e:
        logger.error(f"Diff Agent parse error: {e}")
        return {"score": 50, "summary": "Could not parse diff analysis", "has_bugs": False}
