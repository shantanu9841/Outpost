# Outpost Operating Guide

Read this first, every session. It is the rulebook. The plan lives in @SPEC.md. Current state lives in @PROGRESS.md. History and reasoning live in @DECISIONS.md. The visual system lives in @design.md.

## What Outpost is
A multi-tenant B2B outreach command center. A business logs into its own isolated workspace, describes what it is promoting, and Outpost finds relevant creators (Instagram, TikTok, YouTube) and businesses (distributors, logistics), scores each for fit with cited evidence, drafts personalized outreach, and runs every draft through a human approval queue before anything is sent. It then tracks each target through a pipeline and scores its own draft quality over time.

## Stack
- Backend: Python, FastAPI.
- Database: SQLite, single file at ./outpost.db.
- Frontend: server-rendered HTML with light vanilla JavaScript. No frontend framework.
- One repo, run locally. No Docker, no cloud service required to run or demo.

## Run and verify
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload`
- Open: http://localhost:8000
- After every change, start the server and confirm the affected page loads without error. This is the verification loop. Do not report a slice done until you have run it and shown the output.

## Non-negotiables (these define the product)
1. BYO-key. Every paid external service (Apify, Apollo, paid LLMs) is called with a key the user pastes into their workspace settings. Never hardcode a key. Never call a paid service with your own key. Keys are stored per workspace and masked in the UI.
2. Demo mode. The app must work with zero keys pasted, using the free YouTube source, the free Gemini tier, and seeded sample data. Paid sources activate only when a key is present.
3. Source-agnostic. Discovery talks to a Source interface, not to any one provider. Adding or swapping a source (YouTube, Apify, Apollo) is a config change, not a rewrite.
4. Human approves every send. The agent drafts. A human edits, approves, or rejects. Nothing sends automatically. Every action is written to an audit trail.
5. Structured output. Every model call that returns data uses a Pydantic schema, is validated, and retries on a parse failure.
6. Multi-tenant isolation. Every row belongs to a workspace. No query ever returns another workspace's data.

## Not building
Payments and auto-posting. Do not add Stripe. Do not add posting to any platform. Out of scope, permanently.

## Design
Follow @design.md exactly. Use its tokens as CSS custom properties. Do not invent colors, spacing, or fonts. Light and dark both required.

## Build discipline
- One slice at a time, in the order in @SPEC.md. Do not start the next slice until the current one is verified and committed.
- Use plan mode before writing code for a slice. Confirm the plan against SPEC.md before coding.
- Start of session: read PROGRESS.md and DECISIONS.md.
- End of a slice: update PROGRESS.md (what is done, what is next), append any real decision to DECISIONS.md, and commit to git with a clear message.
- If asked to do something that contradicts a non-negotiable, stop and flag it rather than complying.

## Code conventions
- Keep it simple and readable. This project is maintained by a non-technical owner reading with your help. Prefer clear names and short functions over clever code.
- Comment the why, not the what, and only where it is not obvious.
- No new dependency unless necessary. If you add one, note it in DECISIONS.md.

## Model selection (ask before every slice)
Before starting any slice, recommend which model I should run and wait
for me to switch before proceeding. Principle: use the stronger reasoning
model for planning and architectural judgment; use the faster model for
mechanical execution from an approved plan. State the recommendation as
the first line of every slice, name the current best-fit models by their
in-app names, give a one-line reason, and stop until I confirm the switch.

## Local data
Never reset or delete outpost.db, seed files, or any local state on your
own. If unexpected data is present, inspect it, back it up, and ask.
Local data is the user's, not the agent's.

## Collaboration
Read @collaboration.md at the start of every session. It contains the operating
rules and handoff log for work shared across SDEs and environments.

Only one SDE may implement on a branch or working tree at a time. A second SDE
may review or plan, but must not edit concurrently. Before making changes,
inspect the current branch, latest commit, working-tree status, and the latest
collaboration entry.

Before every commit, append an entry to collaboration.md describing the changes
or corrections included, verification performed, known limitations, and next
action. Include that entry in the same commit. Architectural decisions still
belong in DECISIONS.md, and slice status still belongs in PROGRESS.md.

Never overwrite, delete, reset, or incorporate another SDE's uncommitted work
without explicit owner approval. All other build, verification, documentation,
and commit rules in this file and DECISIONS.md continue to apply.
