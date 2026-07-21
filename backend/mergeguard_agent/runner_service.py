import json
import time
from google.adk.runners import InMemoryRunner
from google.genai import types
from .agent import root_agent
from .scorer import calculate_trust_score

runner = InMemoryRunner(agent=root_agent, app_name="mergeguard")


async def analyze_pr(pr_data: dict, code_context: str) -> dict:
    """
    PR data + code context (diff + full changed-file content) lo,
    ADK pipeline chalao, 5 agents ke results nikaalo, trust score calculate karo
    """
    # ADK ko ek hi message mein context dena hai
    message_text = f"""PR Title: {pr_data['title']}
PR Description: {pr_data.get('description', 'No description')}
PR Author: {pr_data['author']}
Repository: {pr_data['repo']}
Base Branch: {pr_data['base_branch']}
Head Branch: {pr_data['head_branch']}

{code_context}"""

    user_id = "mergeguard_system"
    session_id = f"pr_{pr_data['repo'].replace('/', '_')}_{pr_data['pr_number']}_{int(time.time())}"

    # Session banao
    await runner.session_service.create_session(
        app_name="mergeguard",
        user_id=user_id,
        session_id=session_id,
    )

    content = types.Content(role="user", parts=[types.Part(text=message_text)])

    results = {}

    # Agent run karo, events stream honge har sub-agent se
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    try:
                        parsed = json.loads(part.text)
                        # author batata hai konsa agent bola
                        agent_name = event.author.replace("_agent", "")
                        results[agent_name] = parsed
                    except (json.JSONDecodeError, TypeError):
                        continue

    # Trust score calculate karo
    scoring = calculate_trust_score(results)

    return {
        "results": results,
        "trust_score": scoring["trust_score"],
        "decision": scoring["decision"],
    }