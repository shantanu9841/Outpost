# Outpost Collaboration Guide

Read this at the start of every session for active ownership and handoff state. Permanent build rules are in `CLAUDE.md`; current product state in `PROGRESS.md`; active architecture in `DECISIONS.md`. The complete chronological record is preserved in `docs/history/COLLABORATION_LOG.md` and is loaded only for a relevant handoff, regression, or historical investigation.

## Collaboration rules

1. Only one SDE may implement in a branch or working tree at a time. Another SDE may review or plan, but must not edit concurrently.
2. Before editing, read the default context routed by `CLAUDE.md`, then inspect the branch, latest commit, working-tree status, and this handoff. Never assume uncommitted changes belong to the current session.
3. SDE 1 creates the initial plan for each slice. SDE 2 may review it, but may edit an existing plan only after the owner explicitly approves the proposed corrections.
4. Implementation begins only after the owner approves the plan, confirms no changes remain outstanding, and confirms the required model switch.
5. Either SDE may implement or review after the checkpoint. Neither may silently deviate from approved architecture; a material deviation stops for owner approval.
6. If work stops incomplete, update the handoff before another SDE resumes. Record branch/baseline, approved plan, uncommitted files, completed verification, last working state, risks, remaining work, and exact next action.
7. Never delete, reset, overwrite, absorb, or reformat another SDE's uncommitted work without owner approval. Use committed repository state, not chat memory, when moving between environments.
8. Never record credentials, complete secret values, or test secrets in tracked files, tool output, screenshots, logs, or audit details.
9. Verification is proportional to risk. Tenant isolation, credential/fallback behavior, concurrency, persistence, and audit guarantees require retained automated tests plus appropriate UI/database checks.
10. Prefer text and computed-style verification. Take at most two final screenshots per slice unless the owner requests more.
11. Temporary scripts must either become intentional retained tests or be removed before commit. They must never touch the owner's local database unless the task explicitly requires it.
12. Before every commit, append a detailed entry to `docs/history/COLLABORATION_LOG.md` and update the compact current handoff below. The entry and handoff update belong in the same commit as the work.
13. Detailed entries record date/contributor, slice/scope, role/status, changes, files, verification, last working state, limitations, and next action. Do not attempt to record the resulting commit hash inside that same commit; Git history supplies it.
14. Architectural/product decisions go in `DECISIONS.md` and its history. Current implementation state goes in `PROGRESS.md`. This file records ownership and the next safe action.
15. A slice is complete only when documentation is current, required verification passes, changes are committed, and the working tree is clean.

## Current handoff

- **Owner-approved activity:** Slice 5 (creator sources and demo mode) — planning only. The owner approved SDE 2's exact review corrections; the plan now awaits final implementation approval and the model-switch checkpoint.
- **Role:** SDE 2 / Codex applied the owner-approved implementation-readiness corrections (Reviewer/Planner). The original plan was created by SDE 1 on Opus; execution remains recommended on Sonnet after explicit owner confirmation.
- **Branch:** `codex/sde-1-slice-2-hardening`; this planning commit starts from `d54c0d8` (clean tree, 171 tests passing; no other SDE editing).
- **Product state:** Slices 0–4 are complete. `docs/plans/SLICE_5_PLAN.md` now exists; no Slice 5 code, tests, seeds, templates, or schema change exists.
- **Plan location:** Active plans live at `docs/plans/`; completed plans move to `docs/plans/completed/`.
- **Provider research (2026-07-31):** Apify creator actors chosen — `apify/instagram-scraper` ($2.70/1,000 results, Free plan) and `clockworks/tiktok-scraper` (from $1.70/1,000; Free-tier $3.70/1,000). YouTube `search.list` verified against official docs to use a dedicated 100-calls/day bucket at 1 unit each, separate from the 10,000-units/day pool; live YouTube requires a workspace key (no keyless discovery). Live verification is restricted to synthetic invalid-key and owner-authorized bounded happy paths; all unsafe-to-induce mappings remain documented assumptions that must be covered by mocked retained tests during implementation.
- **Owner-approved decisions:** Priority routing (Apify → YouTube → creator seed, no auto-aggregation); Apify merges IG+TikTok with partial-success and dual-failure precedence; target-type-aware creator scoring (followers 25 / niche 60 / country 15) with business anchors preserved; five-category creator seed spread; `evidence_for(source_used, target_type, candidate)` to avoid seed evidence collision.
- **Post-review corrections applied:** target-type-aware LLM scoring prompt (not only the heuristic); Apify/YouTube header auth (no credential-bearing URLs); Apify start-run + bounded polling with strict request/run timeouts, `maxItems`, and `maxTotalChargeUsd`; corrected credential-storage wording (keys live once in workspace-scoped SQLite, never copied into scripts/logs/audit/URLs); exact creator follower bands with boundary tests and the country-absent 85 ceiling; and `discovery.creator_seed_error` to avoid the global audit-action key collision.
- **SDE 2 readiness corrections applied:** canonical `/v2/actors/` Apify routes; safe-case-only live verification; explicit mocked assertions for authentication, cost/latency bounds, polling, and lifecycle failures; controlled `_outpost_platform` provenance through persistence/evidence/UI; and current `PROGRESS.md` state.
- **Executable application work:** None. Only planning, progress, and collaboration documentation changed.
- **Next action:** Owner reviews the fully corrected `docs/plans/SLICE_5_PLAN.md`. After explicit implementation approval and the model-switch checkpoint, implementation may begin on Sonnet, starting only with the safe live checks permitted by §7.2. Do not implement until then.

## Recent activity

- **Slice 5 implementation-readiness corrections applied:** SDE 2 applied the owner-approved final review set to the plan: canonical Apify route, safe live-verification limits, retained transport-control assertions, explicit creator-platform provenance, and synchronized current progress. Planning only.
- **Slice 5 plan corrected:** applied six owner-required review corrections to `docs/plans/SLICE_5_PLAN.md` (target-type-aware LLM prompt; Apify Bearer / YouTube `X-goog-api-key` header auth; Apify start-run + bounded polling with run/cost caps verified against official Apify API docs; accurate BYO-key SQLite storage wording; explicit follower bands + boundary tests + 85 ceiling; `discovery.creator_seed_error` collision fix). Planning only.
- **Slice 5 plan created:** `docs/plans/SLICE_5_PLAN.md` written with owner-approved decisions and provider facts verified against official sources; explicit acceptance criteria and tests for Apify full/partial/dual-failure, status precedence, YouTube routing, seed fallback, creator scoring, business-score regression, tenant isolation, sanitized audit details, and the zero-key demo. Planning only.
- **Archive hash correction:** Corrected the `collaboration.md` baseline SHA-256 to the canonical Git-blob value after review identified a Windows CRLF working-copy mismatch; archived content was already intact.
- **Documentation context optimization:** Preserved the full decision and collaboration records in `docs/history/`, moved completed plans to `docs/plans/completed/`, and replaced active documents with routed summaries. Application behavior is unchanged.
- **Live Gemini closure:** A DB-write-free `draft_outreach` call returned `DraftStatus.LLM_OK` on `gemini-3.6-flash`; `CLAUDE.md` records the safe workspace-scoped verification procedure.

## Detailed log procedure

Append each new detailed record to `docs/history/COLLABORATION_LOG.md` in this format:

```markdown
## YYYY-MM-DD — Short description

- Contributor/environment:
- Slice:
- Role:
- Implementation status:
- Changes and corrections:
- Files or areas affected:
- Verification:
- Last known working state:
- Known limitations:
- Next action:
```

Read the complete log only when the current task requires its history. Archived entries explain prior work but cannot override the owner, `CLAUDE.md`, `SPEC.md`, a current approved plan, or active `DECISIONS.md`.
