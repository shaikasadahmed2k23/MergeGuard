from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from .sub_agents import (
    security_agent,
    intent_agent,
    diff_agent,
    impact_agent,
    context_agent,
)

# Step 1: Saare 5 analysis agents PARALLEL mein chalao
# Inme se koi bhi ek doosre pe depend nahi karta - isliye parallel safe hai
analysis_pipeline = ParallelAgent(
    name="mergeguard_analysis_pipeline",
    sub_agents=[
        security_agent,
        intent_agent,
        diff_agent,
        impact_agent,
        context_agent,
    ],
    description="Runs all 5 MergeGuard analysis agents in parallel on a PR diff",
)

# Step 2: Root agent - abhi sirf parallel pipeline hai
# Trust scorer aur decision wala part hum Python mein handle karenge (FastAPI side)
# kyunki wo deterministic math hai, LLM ki zaroorat nahi
root_agent = analysis_pipeline