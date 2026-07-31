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

- **Owner-approved activity:** Slice 6 (evaluation and cost-aware routing) — planning only, **v2**. SDE 2 reviewed v1 (`2f991a5`) and the owner approved ten corrections, now applied; the plan is **under owner review again**. Implementation has not begun.
- **Role:** SDE 1 / Claude Code, Planner (correction implementer for this revision). Planned on Opus 4.8; execution recommended on Sonnet after the owner's explicit approval and model-switch confirmation.
- **Branch/baseline:** `codex/sde-1-slice-2-hardening` at `b640b49` (post-fix Slice 5 state), clean tree, 212 passing tests, unchanged by this revision. This planning commit modifies only `docs/plans/SLICE_6_PLAN.md`, `collaboration.md`, and `docs/history/COLLABORATION_LOG.md`.
- **Product state:** Slices 0–5 are complete. `docs/plans/SLICE_6_PLAN.md` (v2) exists (active); no Slice 6 code, tests, schema, or template change exists.
- **Plan location:** Active plans live at `docs/plans/`; completed plans live at `docs/plans/completed/`.
- **Ten SDE 2 corrections applied (plan §0 indexes each to its section):** (1) `app/llm.py`'s `_resolve_key` drops the `GEMINI_API_KEY` environment fallback entirely — a change to already-shipped Slice 2 code, so every LLM workflow becomes strictly workspace-key-only; (2) the single-token `LLMResult` is replaced by a per-attempt `TokenUsage` (model, prompt, candidates, thinking, total — each independently nullable); (3) usage accumulates across every structured-output attempt (first try, retry, and attempts that fall back to a heuristic), attached to `LLMError` itself, never exposing a provider payload or credential; (4) "no model call was made" (`0`, known) and "a call happened but usage is unreadable" (`None`, unknown) are never conflated, end to end through the aggregate; (5) dollar estimates price each attempt at *that attempt's own model's* per-input/output/thinking rate rather than a blended or final-model rate, computed once at creation time into a new `cost_breakdown_json` + integer `estimated_cost_microusd` so historical estimates never drift when pricing constants change; (6) a rejected key discovered during default drafting is now terminal for the whole routing request — eval and escalation make zero further Gemini calls; (7) the `eval` table gets `draft_id INTEGER NOT NULL UNIQUE REFERENCES draft(id)`, enforcing exactly one eval per draft in SQLite; (8) the deterministic heuristic rubric is now fully specified — exact point tables and boundary behavior for all four 0–25 dimensions, a shared `BANNED_FILLER_PHRASES` constant moved out of prose and into `app/agent/drafting.py`, sentence-variety and question-counting algorithms, missing-data behavior, and the exact nested `EvalDimension`/`EvalRubric`/`EvalResult` Pydantic shapes; (9) "free model"/"free tier" language is replaced throughout with "default model" and "estimated paid list-price cost" — default drafting and the LLM judge both spend the workspace owner's real quota once a key is present, and the only genuinely zero-cost state is no key at all; (10) the plan now states explicitly that Slice 6 cannot be marked complete against `SPEC.md` until the owner approves a specific stronger model id and it passes the required verification gate, independent of whether the (disabled, mocked-tested) escalation code is merged.
- **Resolved per owner instruction (previously open in v1 §8):** paid-tier opt-in storage is now a firm decision — a dedicated, idempotently migrated `workspace.paid_tier_enabled INTEGER NOT NULL DEFAULT 0` column (product configuration, not a credential), workspace-scoped, default off for every existing workspace. `HIGH_FIT_THRESHOLD = 85` and `CONFIDENCE_THRESHOLD = 80` (both inclusive) and the 4×0–25 eval scale are kept as proposed.
- **Verification:** Documentation-only. No application code was written or run; the 212-test baseline is unchanged. `git diff --check` clean; credential-pattern scan clean (see commit).
- **Known limitations:** The stronger model id/pricing remain unverified by design (owner-gated, correction 10). `gemini-3.6-flash`'s exact current per-input/output/thinking-token rates are left as explicit placeholders in the plan, to be filled from the official Gemini pricing page immediately before implementation — not fabricated. The plan's own interpretation of "`thoughtsTokenCount` absent within an otherwise-present `usageMetadata` block is a known zero, not unknown" is flagged in §8 for the owner to confirm against current official documentation if desired.
- **Next action:** Owner reviews `docs/plans/SLICE_6_PLAN.md` v2. After explicit implementation approval and the model-switch confirmation, implementation may begin on Sonnet, starting with `models.py`/`llm.py`/`app/agent/drafting.py`'s widened `DraftResult`, then `eval.py`/`routing.py`, then DB/route/UI wiring, then the §6 verification (now 22 acceptance criteria). Do not implement until then.

## Recent activity

- **Slice 6 plan corrected (v2):** applied ten owner-approved SDE 2 review corrections to `docs/plans/SLICE_6_PLAN.md` — workspace-key-only (no env fallback), per-attempt `TokenUsage` with retry/failure accumulation, known-zero-vs-unknown cost semantics, per-model dollar pricing persisted at creation time, terminal invalid-key short-circuit, a SQLite-enforced one-eval-per-draft constraint, a fully specified heuristic rubric, corrected "default model"/"estimated paid" billing language, and explicit Slice 6 completion-gating on the deferred stronger model. Also resolved the paid-tier opt-in storage decision (dedicated `workspace` column, default off). Planning only; under owner review.
- **Slice 6 plan created (v1):** `docs/plans/SLICE_6_PLAN.md` drafted on Opus 4.8 with the owner's four approved decisions (stronger BYO-billed paid tier gated behind a per-workspace opt-in; LLM-judge eval with heuristic fallback; tokens + estimated `$`; deferred stronger-model id/pricing). Planning only; superseded by v2 above.
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
