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

- **Owner-approved activity:** Correct all findings from SDE 2's Slice 5 implementation review.
- **Role:** Codex / SDE 2, implementation reviewer and correction implementer.
- **Branch/baseline:** `codex/sde-1-slice-2-hardening`, correcting Slice 5 implementation commit `b2ddd11`.
- **Product state:** Slices 0–5 are complete after the provider-shape and latency hardening in this correction pass. `docs/plans/completed/SLICE_5_PLAN.md` remains the implemented plan.
- **Plan location:** Active plans live at `docs/plans/` (currently empty); completed plans live at `docs/plans/completed/`.
- **Implementation corrections:** TikTok rows now parse the published nested `authorMeta` shape (with defensive documented/legacy aliases and creator-specific identity fallback); malformed YouTube `search.list` 200 payloads now become typed `PROVIDER_ERROR` outcomes instead of false empty successes; Apify polling rechecks the deadline after sleeping and after each poll response and caps each poll request timeout to the remaining wall-clock budget.
- **Retained coverage:** `tests/test_slice5_creators.py` now includes provider-shaped nested TikTok fixtures, malformed TikTok metadata rejection, malformed YouTube success-payload classification, final-partial-sleep exhaustion, remaining-budget timeout capping, and late poll-response rejection.
- **Verification:** Targeted source regression suite passes 19/19; full retained suite passes 212/212 (`171` pre-Slice-5 plus `41` Slice-5 tests). `git diff --check` is clean. No live provider call or owner database write was needed for this correction.
- **Known limitations:** No owner-authorized live Apify/YouTube happy-path run has been performed; status mappings beyond the safely observed invalid-key cases remain documented assumptions. The TikTok mapping is grounded in the current official schema and retained tests but is still unconfirmed against an owner-authorized live dataset item.
- **Next action:** Owner may review this correction. Slice 6 still requires the model recommendation and plan-mode confirmation mandated by `CLAUDE.md` before implementation.

## Recent activity

- **Slice 5 implemented: creator sources and demo mode.** SDE 1 / Claude Code implemented `docs/plans/completed/SLICE_5_PLAN.md` end to end on Sonnet: YouTube and Apify sources behind the shared `Source` contract, deterministic creator routing priority, target-type-aware scoring (LLM prompt and heuristic), namespaced creator audit/banners, target-type-aware UI, and 35 new retained tests. 206/206 tests pass; verified live in a browser session against the real app.
- **Slice 5 implementation review fixes completed:** corrected TikTok's nested `authorMeta` normalization, malformed YouTube 200 classification, and strict Apify poll-budget enforcement; 212/212 retained tests pass.
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
