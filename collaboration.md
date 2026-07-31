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

- **Owner-approved activity:** Slice 5 (creator sources and demo mode) — implemented, verified, and ready to commit.
- **Role:** SDE 1 / Claude Code, Implementer. Ran on Sonnet per the plan's execution recommendation (confirmed compatible with the plan's model-switch checkpoint: this session's model is Sonnet 5).
- **Branch:** `codex/sde-1-slice-2-hardening`; implemented on top of `3db96c0` (clean tree, 171 tests passing; no other SDE editing detected — a separate worktree on an unrelated branch, `claude/slice-5-creator-sources-3085d8`, was open for this same task but had no Slice 3/4/5 work of its own, so this branch's own checkout at `C:\Users\shant\claude_code_projects\Outpost` was used instead, per this file's rule 1).
- **Product state:** Slices 0–5 are complete. `docs/plans/completed/SLICE_5_PLAN.md` (moved from `docs/plans/`) is the implemented plan; no material deviation from it.
- **Plan location:** Active plans live at `docs/plans/` (now empty); completed plans live at `docs/plans/completed/`.
- **§7.2 live verification performed (2026-07-31):** a temporary, DB-write-free script confirmed, against the real APIs with synthetic bogus credentials only: Apify start-run with a bogus Bearer token → `401`/`user-or-token-not-found`; YouTube `search.list` with a bogus `X-goog-api-key` header → `400`/`INVALID_ARGUMENT`/"API key not valid". Both confirm the plan's `INVALID_KEY` mapping and the header-only auth transport. The script was deleted immediately after (rule 11). The owner-authorized bounded happy-path leg was **not** run — no `youtube`/`apify` workspace key was made available this session — so live creator discovery itself remains unverified beyond this; all other §5.4 mappings remain the plan's documented assumptions, covered by mocked tests only.
- **Implementation:** `app/sources/youtube.py` and `app/sources/apify.py` (new, per §4-§5); `app/sources/base.py` (`SourceStatus.PARTIAL_RESULTS`); `app/sources/seed.py` (`SeedSource("creator")` reads `seeds/creators.json`, no country pre-filter — unlike business — so the geographic-mismatch row reaches scoring); `app/sources/__init__.py` (`_discover_creator` priority routing, `evidence_for(source_used, target_type, candidate)`); `app/agent/scoring.py` (target-type-aware `SYSTEM_PROMPT`/`_build_prompt`, `_heuristic_creator` with exact follower bands, business path untouched); `app/audit_banners.py` (`CREATOR_DISCOVERY_MAP`/`CREATOR_DISCOVERY_OK_ACTIONS`, `discovery_action_for(source_attempted, status)` dispatcher — a small addition beyond the plan's literal §6.4 text, needed because a creator `OK` must resolve to `discovery.apify_ok` or `discovery.youtube_ok` depending on which source actually succeeded, which a status-only map can't express); `app/main.py` (wires the new dispatcher, `_platform_label` for `campaign_detail`); three templates (creator radio enabled, target-type-aware table, corrected YouTube Settings hint); `seeds/creators.json` (5-row strong/partial/geo-mismatch/weak/irrelevant spread, scores 100/80/65/40/5 against a "wellness fitness mindfulness" brief); `tests/test_slice5_creators.py` (35 new tests covering every §7.1 acceptance criterion).
- **Verification:** All 206 tests pass (171 unchanged + 35 new) via `python -m unittest discover -s tests`. Business anchor score (Cornerstone → 90) re-pinned and unchanged. Live browser session (real app, real `outpost.db`, new "Slice 5 Verify" workspace, id 8, left in place as normal product usage) confirmed: creator radio enabled on `/campaigns/new`; a zero-key creator campaign completed end to end (seed discovery → heuristic scoring → target-type-aware table rendering "Creator/Handle/Platform/Followers" headers with YouTube/Instagram/TikTok platform labels correctly distinguishing all three seed platforms → `discovery.no_creator_key` info banner → draft → approve → pipeline stage change, matching the mocked integration test); Settings shows the corrected YouTube hint. Computed-style checks confirmed both themes against design.md tokens exactly (dark: `bg` `#09090B`, `text` `#FAFAFA`, `bg-subtle` `#131316`; light: `bg` `#FAFAFA`, `text` `#18181B`, `bg-subtle` `#F4F4F5`, `.banner--info` background `#DBEAFE` matching `info-subtle`) — no new CSS was added, so no new tokens needed separate validation. Screenshots were unavailable in this session's headless browser pane (same limitation as prior slices); computed-style verification substituted, per collaboration.md rule 10's own preference.
- **Known limitations:** No live Apify/YouTube creator discovery run has been performed (requires an owner-provided key); the §5.4 status mappings beyond `INVALID_KEY` remain documented assumptions per the plan's own §9; TikTok's exact Apify output field names are unconfirmed against a real dataset item (tolerated defensively — see `PROGRESS.md`).
- **Next action:** Commit this work, then Slice 6 (evaluation and cost-aware routing) per `SPEC.md` §6 — model recommendation and plan-mode confirmation still owed to the owner before that slice's implementation begins.

## Recent activity

- **Slice 5 implemented: creator sources and demo mode.** SDE 1 / Claude Code implemented `docs/plans/completed/SLICE_5_PLAN.md` end to end on Sonnet: YouTube and Apify sources behind the shared `Source` contract, deterministic creator routing priority, target-type-aware scoring (LLM prompt and heuristic), namespaced creator audit/banners, target-type-aware UI, and 35 new retained tests. 206/206 tests pass; verified live in a browser session against the real app.
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
