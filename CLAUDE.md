# Outpost Operating Guide

Read this first every session. It contains permanent product and execution rules. Product scope lives in `SPEC.md`; current state in `PROGRESS.md`; active architectural constraints in `DECISIONS.md`; visual rules in `design.md`; coordination and handoff state in `collaboration.md`.

## Context routing

Read only the context required for the task:

- Every session: `CLAUDE.md`, `PROGRESS.md`, `SPEC.md`, `DECISIONS.md`, and `collaboration.md`.
- UI or visual work: also read the relevant parts of `design.md`.
- Planning or implementing a slice: also read that slice's current approved plan and the active decisions it names.
- Regression work in a completed subsystem: read its completed plan under `docs/plans/completed/` and the relevant entries in `docs/history/`.
- Historical investigation: load only the relevant decision or collaboration history, not the complete archives by default.

Completed plans and history explain prior reasoning; they are not active instructions unless a current document routes you to them.

When documents conflict, apply this order: current explicit owner instruction; this guide; `SPEC.md`; current approved slice plan; active `DECISIONS.md`; current `PROGRESS.md` and handoff; implemented code and retained tests; historical archives. Stop for owner direction if a material conflict remains.

## What Outpost is

A multi-tenant B2B outreach command center. A business describes what it promotes; Outpost finds relevant businesses and creators, scores fit with cited evidence, drafts grounded outreach, requires human approval, tracks targets through a pipeline, and later evaluates draft quality and cost.

## Stack

- Python, FastAPI, SQLite.
- Server-rendered HTML and light vanilla JavaScript.
- One local repository; no Docker or cloud deployment required.

## Run and verify

- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload`
- Open: http://localhost:8000
- After each change, run proportional automated verification and load the affected page or workflow. Do not report completion without showing the result.

## Non-negotiables

1. **BYO-key.** External services use keys pasted by the owner into workspace settings. Never hardcode, expose, copy between workspaces, or use an agent-owned key.
2. **Demo mode.** The app must complete with zero keys through free paths and seeded data.
3. **Source-agnostic.** Discovery depends on the shared Source contract, never directly on one provider.
4. **Human approval.** Nothing sends automatically. A human edits, approves, or rejects every draft, and every action is audited.
5. **Structured output.** Model data uses Pydantic schemas, validation, and one parse retry.
6. **Tenant isolation.** Every tenant row and query is scoped by `workspace_id`; cross-workspace data must never be exposed.
7. **Atomic audit.** When an action requires an audit row, the state mutation and audit commit together or neither remains.
8. **Local data belongs to the owner.** Never reset, delete, or silently rewrite `outpost.db`, seed files, credentials, or other local state.

## Live provider verification

- Keys are workspace-scoped, never global. Locate an eligible workspace using metadata only: workspace id/name, `key_name`, `length(key_value)`, and `created_at`.
- Never query raw `key_value` merely to inspect it, and never print, log, paste, copy, or commit it. Provider code may consume it via `db.get_settings()` inside the verification process.
- The currently approved Gemini verification workspace is `Slice 3 Verify` (workspace id `5`). Its setting passed a DB-write-free `draft_outreach` call against `gemini-3.6-flash` on 2026-07-31 with `DraftStatus.LLM_OK`.
- For a full UI flow in another workspace, ask the owner to paste the key through that workspace's Settings page. Never duplicate it directly in SQLite.
- If the approved workspace or setting is missing, stop and ask the owner. Do not search files, environment history, logs, or Git for credentials.

## Not building

Payments and automatic posting or sending are permanently out of scope. Do not add Stripe or platform-posting integrations.

## Design

Follow `design.md` for visual work. Use its tokens; do not invent colors, spacing, or fonts. Light and dark themes are both required.

## Build discipline

- Build one slice at a time in `SPEC.md` order.
- Use plan mode and confirm the plan against `SPEC.md` before implementation.
- Do not begin implementation while approved-plan changes are outstanding.
- Do not silently deviate from approved architecture. Stop for owner approval if implementation requires a material change.
- Preserve unrelated or uncommitted user/SDE work.
- A slice is complete only when required documentation is current, verification passes, changes are committed, and the working tree is clean.

## Code conventions

Keep code simple and readable for a non-technical owner. Prefer clear names and short functions. Comment why, not what. Add no dependency unless necessary and record the decision.

## Model selection

Before each slice, recommend the best available planning and execution models by their in-app names, explain the choice in one line, and wait for the owner to confirm the switch. Use the stronger reasoning model for planning or architectural judgment and the faster model for mechanical execution from an approved plan.

## Collaboration

Read `collaboration.md` for active roles, ownership, and handoff state. Only one SDE may implement in a working tree at a time; another may review or plan without editing concurrently.

Before editing, inspect the branch, latest commit, working-tree status, and current handoff. Before every commit, append the detailed record to `docs/history/COLLABORATION_LOG.md` and update the compact handoff in `collaboration.md`. Product decisions go in `DECISIONS.md`; current state goes in `PROGRESS.md`.
