from google.adk.agents import Agent
from pydantic import BaseModel, Field
from typing import List


# ============================================
# SECURITY AGENT
# ============================================

class SecurityAnalysis(BaseModel):
    has_critical_issues: bool = Field(description="True if critical security issues found")
    has_warnings: bool = Field(description="True if minor warnings found")
    critical_issues: List[str] = Field(description="List of critical security issues, empty if none")
    warnings: List[str] = Field(description="List of warnings, empty if none")
    severity: str = Field(description="One of: critical, high, medium, low, none")
    score: int = Field(description="Security score from 0-100")
    summary: str = Field(description="One line security summary")


security_agent = Agent(
    name="security_agent",
    model="gemini-2.5-flash",
    description="Analyzes code diffs for security vulnerabilities",
    instruction="""You are a senior security engineer reviewing a code diff for security vulnerabilities.

Carefully check for:
1. Hardcoded secrets, passwords, API keys, tokens
2. SQL injection vulnerabilities
3. Command injection (eval, exec, os.system, subprocess)
4. Sensitive data exposure in logs or responses
5. Insecure dependencies or imports
6. Authentication/authorization bypasses
7. Path traversal vulnerabilities

Scoring guide:
- Critical issue found (hardcoded secret, injection) -> score 0-30
- High severity warnings -> score 31-55
- Medium warnings -> score 56-75
- Minor or no issues -> score 76-100

You will receive the PR title, author, and code diff. Analyze it carefully and respond with structured output.""",
    output_schema=SecurityAnalysis,
    output_key="security_result",
)

# ============================================
# INTENT AGENT
# ============================================

class IntentAnalysis(BaseModel):
    intent_clear: bool = Field(description="True if the PR description clearly states intent")
    intent_matches_code: bool = Field(description="True if actual code matches stated intent")
    stated_intent: str = Field(description="What the developer said they did")
    actual_implementation: str = Field(description="What the code actually does")
    mismatch_details: str = Field(description="Describe any mismatch, or 'none'")
    hidden_changes: bool = Field(description="True if there are unexplained extra changes")
    hidden_changes_detail: str = Field(description="Describe hidden changes, or 'none'")
    score: int = Field(description="Intent match score from 0-100")
    summary: str = Field(description="One line intent analysis summary")


intent_agent = Agent(
    name="intent_agent",
    model="gemini-2.5-flash",
    description="Analyzes whether the PR's stated intent matches its actual code implementation",
    instruction="""You are an expert code reviewer analyzing whether a pull request's stated intent matches its actual implementation.

You will receive: PR Title, PR Description, and the code diff.

Your job:
1. Understand what the developer SAID they did (from title + description)
2. Understand what the developer ACTUALLY did (from the diff)
3. Check if these match

Look for:
- Does the code change align with the stated purpose?
- Are there unexpected changes unrelated to the stated intent?
- Is the scope appropriate for what was described?
- Does the PR do MORE than described (hidden changes)?
- Does the PR do LESS than described (incomplete implementation)?

If no description is provided, treat intent_clear as false and penalize the score heavily (around 30).

Scoring guide:
- Intent clearly matches code, nothing hidden -> score 85-100
- Minor mismatch or incomplete -> score 60-84
- Significant mismatch or hidden changes -> score 30-59
- No description or completely wrong -> score 0-29""",
    output_schema=IntentAnalysis,
    output_key="intent_result",
)


# ============================================
# DIFF AGENT (Code Quality)
# ============================================

class DiffAnalysis(BaseModel):
    has_bugs: bool = Field(description="True if bugs are found in the diff")
    bug_details: str = Field(description="Describe bugs found, or 'none'")
    code_quality: str = Field(description="One of: good, moderate, poor")
    quality_details: str = Field(description="Explain quality issues")
    score: int = Field(description="Code quality score from 0-100")
    summary: str = Field(description="One line summary of the diff analysis")


diff_agent = Agent(
    name="diff_agent",
    model="gemini-2.5-flash",
    description="Analyzes code diff for bugs and code quality",
    instruction="""You are an expert code reviewer. Analyze the given code diff carefully for bugs, logical errors, and code quality.

You will receive: PR Title, PR Description, and the code diff.

Check for:
- Logical errors or bugs
- Incomplete implementations (empty functions, missing logic)
- Code quality (readability, structure, documentation)
- Whether the diff actually achieves what it claims to do

Scoring guide:
- Clean, well-documented, working code -> score 85-100
- Minor quality issues but functional -> score 60-84
- Incomplete or has noticeable issues -> score 30-59
- Empty, broken, or non-functional -> score 0-29""",
    output_schema=DiffAnalysis,
    output_key="diff_result",
)


# ============================================
# IMPACT AGENT
# ============================================

class ImpactAnalysis(BaseModel):
    has_breaking_changes: bool = Field(description="True if breaking changes detected")
    breaking_changes: List[str] = Field(description="List of breaking changes, empty if none")
    missing_imports: bool = Field(description="True if imports seem missing")
    missing_imports_detail: str = Field(description="Details or 'none'")
    needs_migration: bool = Field(description="True if database migration is needed")
    undocumented_env_vars: List[str] = Field(description="New env vars not documented, empty if none")
    performance_concerns: bool = Field(description="True if performance issues are likely")
    performance_details: str = Field(description="Details or 'none'")
    tests_updated: bool = Field(description="True if tests were added or updated")
    risk_level: str = Field(description="One of: high, medium, low")
    score: int = Field(description="Impact score from 0-100")
    summary: str = Field(description="One line impact analysis summary")


impact_agent = Agent(
    name="impact_agent",
    model="gemini-2.5-flash",
    description="Analyzes the potential impact and side effects of a code change",
    instruction="""You are a senior backend engineer analyzing the potential impact and side effects of a code change.

You will receive: PR Title, PR Description, Base Branch, and the code diff.

Carefully analyze for:
1. Breaking changes - function/method signatures changed, API contracts broken
2. Missing imports - new dependencies used but not imported
3. Deleted code - anything removed that might be used elsewhere
4. Database changes - schema changes without migrations
5. New environment variables - added but not documented
6. Performance impact - obvious regressions (N+1 queries, inefficient loops)
7. Test coverage - are tests updated to cover the new changes?

Scoring guide:
- No breaking changes, tests updated, clean -> score 80-100
- Minor impact, low risk -> score 60-79
- Breaking changes or missing tests -> score 35-59
- High risk, breaking changes + no tests -> score 0-34""",
    output_schema=ImpactAnalysis,
    output_key="impact_result",
)


# ============================================
# CONTEXT AGENT
# ============================================

class ContextAnalysis(BaseModel):
    branch_name_good: bool = Field(description="True if branch name follows good conventions")
    code_style_consistent: bool = Field(description="True if code style looks consistent")
    pr_focused: bool = Field(description="True if PR is focused on one thing")
    has_documentation: bool = Field(description="True if there are comments/docstrings where needed")
    issues: List[str] = Field(description="List of context issues found, empty if none")
    positives: List[str] = Field(description="List of good things found")
    score: int = Field(description="Context score from 0-100")
    summary: str = Field(description="One line context analysis summary")


context_agent = Agent(
    name="context_agent",
    model="gemini-2.5-flash",
    description="Reviews the PR for code consistency, project fit, and structure",
    instruction="""You are a senior software architect reviewing a pull request for code consistency and project fit.

You will receive: PR Title, PR Description, Branch names, Repository name, and the code diff.

Analyze:
1. Branch naming - is it meaningful and follows conventions (feature/, fix/, hotfix/, test/, etc.)?
2. Code style - does it look consistent with good practices?
3. File placement - are files being modified/added in appropriate locations?
4. Scope - is this PR focused or does it touch too many unrelated things?
5. Documentation - are there comments/docstrings where needed?

Scoring guide:
- Well structured, focused, good naming -> score 80-100
- Minor issues with style or naming -> score 60-79
- Unfocused PR touching many things -> score 40-59
- Poor structure, no conventions followed -> score 0-39""",
    output_schema=ContextAnalysis,
    output_key="context_result",
)