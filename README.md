Bismillah! Pehle skill check karta hoon markdown ke liye, phir likhta hoon — **depth ke saath, har cheez cover karte hue.**

---

```markdown
# MergeGuard

> Autonomous Multi-Agent Code Review System — built on Google ADK + Gemini

MergeGuard is an AI-powered pull request review system that doesn't just comment on code — it understands intent, evaluates risk, tracks developer trust over time, and makes autonomous merge decisions while knowing exactly when *not* to act alone.

It was built to answer one question honestly: **when can we actually trust an AI agent to take an irreversible action like merging code, and when should it step back?**

---

## Table of Contents

1. [The Problem](#the-problem)
2. [What MergeGuard Does](#what-mergeguard-does)
3. [Why Trust Is Hard — And How We Address It](#why-trust-is-hard--and-how-we-address-it)
4. [System Architecture](#system-architecture)
5. [The Five Analysis Agents](#the-five-analysis-agents)
6. [Trust Scoring](#trust-scoring)
7. [Blast Radius — Risk-Bounded Autonomy](#blast-radius--risk-bounded-autonomy)
8. [Developer Trust Profile](#developer-trust-profile)
9. [Discord Notifications](#discord-notifications)
10. [Tech Stack](#tech-stack)
11. [Project Structure](#project-structure)
12. [Setup & Installation](#setup--installation)
13. [How a PR Flows Through the System](#how-a-pr-flows-through-the-system)
14. [Known Limitations](#known-limitations)
15. [Roadmap](#roadmap)
16. [Testing Evidence](#testing-evidence)

---

## The Problem

Code review today has a structural bottleneck: every pull request, regardless of its actual risk, waits for a human. A one-line typo fix and a database migration both sit in the same queue. Senior engineers spend hours on reviews that don't need their judgment, while genuinely risky changes sometimes slip through because reviewers are fatigued from reviewing everything.

Existing AI code review tools (CodeRabbit, GitHub Copilot Review, Sourcery) solve part of this — they generate suggestions. But none of them make an actual decision. A human still has to read the AI's comment, form their own judgment, and click merge. The AI assists; it doesn't act.

MergeGuard was built to explore a different question: **what would it take for an AI system to safely take the action itself** — for the cases where that's genuinely safe — while reliably identifying the cases where it isn't?

---

## What MergeGuard Does

When a pull request is opened on a connected repository:

1. A webhook fires and MergeGuard fetches the full diff
2. Five specialized AI agents analyze the PR in parallel — security, intent alignment, code quality, system impact, and structural context
3. A deterministic risk classifier (**Blast Radius**) evaluates how sensitive the affected area is
4. The developer's historical track record (**Trust Profile**) is factored in
5. A final decision is made: **auto-merge**, **merge with warning**, **reject**, or **route to human review**
6. A detailed, explainable comment is posted on the PR
7. If the PR needs human attention, a Discord notification is sent to the team
8. Everything is logged to a database and visible on a live dashboard

No part of this is a black box — every decision traces back to specific agent outputs, specific risk factors, and specific historical data, all visible in the PR comment itself.

---

## Why Trust Is Hard — And How We Address It

This was the central design question behind MergeGuard, and we want to be upfront about it rather than oversell what's solved.

### "Why should I trust an AI to make an irreversible decision?"

We don't ask anyone to trust a single score. Trust is built from four independent layers, and **all four must agree** before the system acts autonomously:

- **Multi-agent consensus** — five agents must independently agree the PR is safe, each looking at a different dimension (not one model giving one opinion)
- **Risk-bounded autonomy** — even a perfect score does not grant autonomy if the change touches a sensitive area (see Blast Radius below)
- **Historical accountability** — a developer's track record is part of the equation, not just the PR in isolation
- **Non-negotiable security override** — a critical security finding rejects the PR regardless of every other score

### "How can it judge a PR without understanding the whole codebase?"

It can't, and we don't claim it can. This is a real, unsolved problem in AI code review generally — true whole-repository reasoning is expensive and still an open research problem. Our answer is **risk-bounded autonomy**: MergeGuard only acts alone on changes with a small, provable blast radius (isolated files, no sensitive keywords, no schema changes). Anything with a wider potential impact is automatically routed to a human, with the agents' findings attached so the human's review is faster, not replaced.

### "What happens when it's wrong?"

Every decision is logged with full reasoning — which agent scored what, why, and what the final decision was. If a bad merge happens, the exact point of failure is traceable, not hidden inside an opaque model call. This is the same principle audit trails serve in regulated industries like finance; we're applying it to code review.

### What we have *not* solved (and say so honestly)

Real developer intent often lives outside the PR description — in Slack threads, in meeting decisions, in unwritten team conventions. MergeGuard currently reasons only from what's written in the PR title, description, and diff. We see this as the next genuinely hard problem worth solving (see Roadmap), and we'd rather name it clearly than pretend it's handled.

---

## System Architecture

```
GitHub PR Event
       │
       ▼
  Webhook (FastAPI) ── signature verified (HMAC)
       │
       ▼
  Diff fetched from GitHub API
       │
       ├──────────────► Blast Radius Calculator (deterministic)
       │
       ├──────────────► Developer Trust Profile (from history)
       │
       ▼
  ADK ParallelAgent
       │
   ┌───┼───┬───┬───┐
   ▼   ▼   ▼   ▼   ▼
 Security Intent Diff Impact Context   (all run concurrently via Gemini)
   │   │   │   │   │
   └───┴───┴───┴───┘
       │
       ▼
  Trust Scorer (weighted, deterministic Python)
       │
       ▼
  Decision Engine
       │
   ┌───┼─────────┬──────────────┐
   ▼   ▼         ▼              ▼
Approve Reject  Warn      Human Review Required
   │   │         │              │
   └───┴─────────┴──────────────┘
       │
       ├──► GitHub comment posted (full breakdown)
       ├──► Merge / close PR via GitHub API (if applicable)
       ├──► Discord notification (if human review needed)
       └──► Saved to Supabase → visible on live dashboard
```

A key design decision: **scoring and risk classification are deterministic Python, not LLM calls.** The five analysis agents use Gemini because they require genuine reasoning (does this code do what it claims? is this a security risk?). But combining scores into a final number, or checking if a diff touches sensitive keywords, doesn't need an LLM — it needs to be fast, predictable, and explainable. We only use the model where understanding is actually required.

---

## The Five Analysis Agents

All five run in parallel via ADK's `ParallelAgent`, each backed by Gemini 2.5 Flash with a structured Pydantic output schema (not free-text — the model is constrained to return a specific JSON shape every time).

| Agent | What It Checks |
|---|---|
| **Security Agent** | Hardcoded secrets, SQL/command injection, insecure auth logic, exposed sensitive data. Includes a fast local regex pre-scan before the LLM call. |
| **Intent Agent** | Whether the PR description's *stated* purpose matches what the diff *actually* does. Flags hidden changes, incomplete implementations, and missing descriptions. |
| **Diff Agent** | Code quality, logical bugs, whether the implementation is complete and functional (not just syntactically valid). |
| **Impact Agent** | Breaking changes, missing imports, undocumented new environment variables, missing test coverage, performance regressions. |
| **Context Agent** | Branch naming conventions, code style consistency, whether the PR is focused or touches unrelated things. |

Each agent returns a 0–100 score plus a structured explanation — never just a number.

---

## Trust Scoring

The five agent scores are combined with fixed weights, reflecting that not all dimensions carry equal risk:

```
Security  → 30%
Diff      → 25%
Intent    → 20%
Impact    → 15%
Context   → 10%
```

This produces a **raw trust score**, which is then adjusted (±5 points) by the developer's trust profile before the final decision is made.

**Override rule:** if the Security Agent flags a critical issue (e.g. SQL injection, hardcoded secret), the PR is rejected immediately regardless of the combined score. No score can compensate for a critical security flaw.

---

## Blast Radius — Risk-Bounded Autonomy

This is the core safety mechanism that prevents MergeGuard from being "confidently wrong" on high-stakes changes.

Before the AI agents even run, a deterministic classifier scans the diff for risk signals:

- Number of files changed
- Sensitive keywords (`auth`, `password`, `token`, `secret`, `payment`, `migration`, `.env`, `config`, etc.)
- Critical file types (`.sql`, `Dockerfile`, environment files)
- Database schema changes
- Disproportionate deletions relative to additions

This produces a `LOW` / `MEDIUM` / `HIGH` classification.

**The rule that makes this matter: a `HIGH` blast radius PR is never auto-merged, no matter how high the trust score is.**

We've tested this directly — a PR scoring 95/100 (clean code, no security issues, perfectly matched intent) was still routed to human review because it touched session/auth configuration. The system explicitly told the reviewer: *"MergeGuard does not auto-merge high blast-radius changes, regardless of trust score."*

This is the answer to "how do you know it won't make a catastrophic autonomous decision" — it structurally can't, on anything we've classified as high-risk, regardless of how confident the analysis is.

---

## Developer Trust Profile

MergeGuard tracks each developer's history within a repository:

```
total_prs, approval_rate, average_score
        │
        ▼
trust_level: "new" | "building" | "trusted" | "needs_scrutiny"
```

- **New** — first PR, no history, standard scrutiny
- **Building** — under 5 PRs, or mixed results — no adjustment yet
- **Trusted** — 5+ PRs, 80%+ approval rate, 80+ average score — small positive score adjustment (+5)
- **Needs scrutiny** — high historical rejection rate — small negative adjustment (−5)

This adjustment **only ever shifts the score within Low/Medium blast-radius cases** — it never overrides a High blast-radius classification or a security rejection. Trust is earned contextually, not as a blanket pass.

---

## Discord Notifications

Every PR decision is posted to a connected Discord channel, with the format adjusted by urgency:

- **Human review required** → `@here` mention, red embed, marked "ACTION NEEDED"
- **Rejected** → red embed, no mention
- **Merged with warnings** → amber embed
- **Approved & merged** → green embed

This solves a real adoption problem: reviewers don't live in GitHub notifications, but most engineering teams already live in Slack/Discord. The goal is that a team lead never has to actively check GitHub to know whether something needs their attention — the system tells them, and only pings loudly when it genuinely matters.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Multi-agent orchestration | **Google ADK (Agent Development Kit)** — `ParallelAgent` for concurrent analysis |
| LLM | **Gemini 2.5 Flash** (Google AI Studio) |
| Structured outputs | Pydantic schemas via ADK `output_schema` |
| Backend | FastAPI (Python) |
| Database | Supabase (PostgreSQL) |
| Frontend | HTML/CSS/JS dashboard (no framework — intentionally lightweight) |
| Notifications | Discord Webhooks |
| Version control integration | GitHub REST API + Webhooks (HMAC-verified) |
| Planned deployment | Google Cloud Run |

---

## Project Structure

```
mergeguard/
├── backend/
│   ├── main.py                    # FastAPI entry point, API routes
│   ├── config.py                  # Environment variable loading
│   │
│   ├── mergeguard_agent/          # ADK agent definitions
│   │   ├── agent.py               # ParallelAgent assembly (root_agent)
│   │   ├── sub_agents.py          # 5 agent definitions + Pydantic schemas
│   │   ├── scorer.py              # Trust score calculation
│   │   └── runner_service.py      # ADK Runner wrapper — analyze_pr()
│   │
│   ├── webhook/
│   │   └── github.py              # GitHub webhook receiver
│   │
│   ├── middleware/
│   │   └── auth.py                # HMAC webhook signature verification
│   │
│   ├── core/
│   │   ├── orchestrator.py        # Pipeline coordination
│   │   ├── blast_radius.py        # Deterministic risk classifier
│   │   ├── trust_profile.py       # Developer history analysis
│   │   └── decision.py            # Final decision logic + comment building
│   │
│   ├── github/
│   │   └── api.py                 # GitHub API — comment, merge, close
│   │
│   ├── database/
│   │   └── models.py              # Supabase read/write
│   │
│   ├── notifications/
│   │   └── discord_notifier.py    # Discord webhook integration
│   │
│   └── logs/
│       └── logger.py              # Structured logging
│
└── frontend/
    └── index.html                 # Live dashboard (stats, PR history, detail modal)
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- A GitHub repository you have admin access to (for webhook setup)
- A Google AI Studio API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free tier available)
- A Supabase project (free tier)
- A Discord server (optional, for notifications)

### 1. Clone and install

```bash
git clone <this-repo-url>
cd mergeguard/backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in `backend/`:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key
GITHUB_WEBHOOK_SECRET=generate_a_random_secret
GITHUB_TOKEN=your_github_personal_access_token
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key
DISCORD_WEBHOOK_URL=your_discord_channel_webhook_url
```

### 3. Set up the database

Run this in your Supabase SQL Editor:

```sql
CREATE TABLE pr_reviews (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  repo TEXT NOT NULL,
  pr_number INTEGER NOT NULL,
  pr_title TEXT,
  pr_author TEXT,
  pr_url TEXT,
  trust_score INTEGER,
  decision TEXT,
  security_score INTEGER,
  security_severity TEXT,
  security_issues JSONB DEFAULT '[]',
  intent_score INTEGER,
  intent_matches BOOLEAN,
  diff_score INTEGER,
  has_bugs BOOLEAN,
  impact_score INTEGER,
  risk_level TEXT,
  context_score INTEGER,
  blast_radius_level TEXT,
  blast_radius_reasons JSONB DEFAULT '[]',
  developer_trust_level TEXT,
  developer_trust_note TEXT,
  full_results JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4. Run the server

```bash
uvicorn main:app --reload
```

### 5. Expose it for GitHub (local development)

```bash
ngrok http 8000
```

### 6. Register the GitHub webhook

In your repository: **Settings → Webhooks → Add webhook**

- Payload URL: `https://<your-ngrok-or-deployed-url>/webhook/github`
- Content type: `application/json`
- Secret: same value as `GITHUB_WEBHOOK_SECRET`
- Events: select **Pull requests**

### 7. Open the dashboard

Open `frontend/index.html` directly in a browser. It connects to `http://localhost:8000` by default — update the `API` constant in the file if your backend runs elsewhere.

---

## How a PR Flows Through the System

1. A developer opens a PR against the connected repository
2. GitHub sends a webhook event; the signature is verified with HMAC
3. MergeGuard fetches the full diff via the GitHub API
4. The Blast Radius classifier runs (instant, deterministic)
5. The developer's Trust Profile is pulled from history (instant, deterministic)
6. All five agents analyze the diff in parallel via Gemini (~10–20 seconds)
7. Scores are combined with weights, then adjusted by trust profile
8. The decision engine applies, in order: security override → blast radius gate → score thresholds
9. A detailed comment is posted to the PR explaining every factor
10. The PR is merged, closed, or left open for human review, accordingly
11. If human review is needed, Discord is notified with `@here`
12. The full record is saved to Supabase and appears on the dashboard immediately

---

## Known Limitations

We'd rather state these directly than have them discovered:

- **No whole-repository reasoning.** Agents see the diff and PR metadata, not the entire codebase. This is a known, hard, unsolved problem in this space generally — see Roadmap.
- **Intent is reconstructed only from what's written.** Real intent that lives in Slack/team discussions outside the PR isn't currently visible to the agents.
- **Free-tier Gemini rate limits.** The current setup uses the Gemini free tier (20 requests/day per key during testing), which is sufficient for development but would need a paid tier or key rotation for production-scale or live demo use.
- **Single-repository trust profiles.** Developer trust is currently tracked per-repository, not across an organization.
- **No automated test execution.** The Impact Agent identifies *missing* tests but doesn't run existing test suites as part of the decision.

---

## Roadmap

**Near-term**
- Deploy to Google Cloud Run for a permanent, publicly testable endpoint
- Configurable notification verbosity (all PRs vs. high-priority only)
- Dashboard view of the full team's trust profiles (not just per-PR detail)

**Medium-term**
- **Multi-source intent reconstruction** via MCP (Model Context Protocol) — pulling targeted, keyword-relevant context from connected Slack/Discord channels rather than relying solely on the PR description. This directly addresses our biggest known limitation above.
- GitHub App packaging, so any repository can install MergeGuard in one click rather than self-hosting
- Per-organization trust profiles instead of per-repository

**Long-term**
- Automated test execution as part of the Impact Agent's evaluation
- Configurable blast-radius rules per organization (teams can define their own sensitive-area keywords)

---

## Testing Evidence

This isn't a concept demo — it has been run against 13+ real pull requests on a live GitHub repository, covering:

- Clean, well-documented code → correctly auto-merged (88–93/100)
- Incomplete/empty implementations → correctly rejected (0–49/100)
- SQL injection in auth code → correctly force-rejected regardless of other scores
- Clean code in a sensitive area (auth/session config) → correctly routed to human review despite a 95/100 score
- A real logical bug in token-refresh logic → correctly caught by the Diff Agent
- A subtle ReDoS vulnerability in an email-validation regex → correctly caught by the Security Agent

Every one of these is traceable in the project's PR history and Supabase logs.

---

## Built For

AI House × Google for Developers — AI Agent Builder Series 2026 (Open Innovation track)

---

*MergeGuard does not claim to replace human code review. It claims to know, precisely and explainably, when it shouldn't try to.*
```

---

Bhai ye poora README hai — **GitHub pe daal do**, team ko bhejo padhne ke liye. Jab sab confirm kar dein, bata — **deploy karte hain Cloud Run pe.** 🚀