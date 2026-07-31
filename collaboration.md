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

- **Owner-approved activity:** Slice 6 (evaluation and cost-aware routing) — planning only, **v3**. SDE 2 reviewed v2 (`cc2c23c`) and the owner approved five further corrections, now applied; the plan is **under owner review again**. Implementation has not begun.
- **Role:** SDE 1 / Claude Code, Planner (correction implementer for this revision). Planned on Opus 4.8; execution recommended on Sonnet after the owner's explicit approval and model-switch confirmation.
- **Branch/baseline:** `codex/sde-1-slice-2-hardening` at `b640b49` (post-fix Slice 5 state), clean tree, 212 passing tests, unchanged by this revision. This planning commit modifies only `docs/plans/SLICE_6_PLAN.md`, `collaboration.md`, and `docs/history/COLLABORATION_LOG.md`.
- **Product state:** Slices 0–5 are complete. `docs/plans/SLICE_6_PLAN.md` (v3) exists (active); no Slice 6 code, tests, schema, or template change exists.
- **Plan location:** Active plans live at `docs/plans/`; completed plans live at `docs/plans/completed/`.
- **Five SDE 2 corrections applied against v2 (plan §0.2 indexes each to its section):** (1) "no request issued" is now the *only* state that may equal known-zero cost — every issued Gemini HTTP attempt (transport failure, non-2xx, malformed/non-JSON 200, or missing/malformed `usageMetadata`) now produces a `TokenUsage` record with unknown fields, rather than v2's bug of letting a failed-but-issued attempt disappear from the usage list and get miscounted as "no calls made"; known usage from attempts preceding a failure is still preserved, while the aggregate becomes unknown if any issued attempt is unknown; (2) the separate `"thinking"` price is removed from `PRICING_USD_PER_MILLION_TOKENS` — Google prices output inclusive of thinking tokens for these tool-free calls, so the dollar formula is now `promptTokenCount × input_rate` plus `(totalTokenCount − promptTokenCount) × output_rate`, requiring known non-negative prompt/total with `total >= prompt`, otherwise unknown; `candidatesTokenCount`/`thoughtsTokenCount` remain stored for visibility only; (3) an omitted `thoughtsTokenCount` is no longer auto-zero — it's unknown by default unless safely derivable (`total == prompt + candidates` → derived zero; `total > prompt + candidates` → derived non-negative difference), with a new `thinking_tokens_derived` boolean on `TokenUsage` distinguishing provider-reported from derived values; (4) fixed a real contradiction in v2's `route_and_draft` signature, which took no `workspace_id` yet called `db.get_paid_tier_enabled(workspace_id)` internally — routing now takes an explicit `paid_tier_enabled: bool` keyword argument and performs no database access at all; `main.py` resolves the flag from its own already-scoped `workspace_id` and passes it in; (5) Gemini authentication switches from the credential-bearing `?key=` query parameter (carried over unexamined since Slice 2) to the `x-goog-api-key` header, matching Slice 5's Apify/YouTube precedent — folded into this slice's existing `_call_gemini` refactor rather than deferred, so v2's "out of scope" note for this is removed.
- **Preserved from v2, unchanged:** strict workspace-key-only (no env fallback); `HIGH_FIT_THRESHOLD = 85` / `CONFIDENCE_THRESHOLD = 80` (both inclusive); dedicated `workspace.paid_tier_enabled`, default off; LLM judge with the fully specified deterministic rubric fallback; per-attempt retry accounting; terminal invalid-key behavior; atomic draft/eval/cost/audit persistence; SQLite-enforced one eval per draft; "estimated paid list-price" wording; no paid live verification without explicit owner authorization; Slice 6 completion gated on the stronger model being owner-approved and verification-gated.
- **Verification:** Documentation-only. No application code was written or run; the 212-test baseline is unchanged. `git diff --check` clean; credential-pattern scan clean (see commit).
- **Known limitations:** The stronger model id/pricing remain unverified by design (owner-gated). `gemini-3.6-flash`'s exact current per-input/output-token rates (now two, not three, per model) are left as explicit placeholders, to be filled from the official Gemini pricing page immediately before implementation — not fabricated. The plan's `thoughtsTokenCount`-derivation rule and its new decoupling of `cost_tokens`/`estimated_cost_microusd` unknown-ness are both flagged in §8 as interpretations the owner may want to confirm or simplify.
- **Next action:** Owner reviews `docs/plans/SLICE_6_PLAN.md` v3. After explicit implementation approval and the model-switch confirmation, implementation may begin on Sonnet, starting with `models.py`/`llm.py` (including the header-auth and per-attempt-usage refactor)/`app/agent/drafting.py`'s widened `DraftResult`, then `eval.py`/`routing.py`, then DB/route/UI wiring, then the §6 verification (now 32 acceptance criteria). Do not implement until then.

## Recent activity

- **Slice 6 plan corrected (v3):** applied five owner-approved SDE 2 review corrections against v2 to `docs/plans/SLICE_6_PLAN.md` — "no request issued" as the only known-zero state (fixing a real bug where a failed-but-issued attempt could be miscounted as zero calls), removed the separate thinking-token price and corrected the dollar formula to prompt-at-input-rate plus remaining-total-at-output-rate, replaced auto-zero thinking-token inference with a safely-derived-or-unknown rule plus a provenance flag, fixed a real signature contradiction in `route_and_draft` (it referenced `workspace_id` without receiving it) by making routing a pure function that takes `paid_tier_enabled` explicitly, and moved Gemini authentication from a credential-bearing query parameter to the `x-goog-api-key` header. Planning only; under owner review.
- **Slice 6 plan corrected (v2):** applied ten owner-approved SDE 2 review corrections to `docs/plans/SLICE_6_PLAN.md` — workspace-key-only (no env fallback), per-attempt `TokenUsage` with retry/failure accumulation, known-zero-vs-unknown cost semantics, per-model dollar pricing persisted at creation time, terminal invalid-key short-circuit, a SQLite-enforced one-eval-per-draft constraint, a fully specified heuristic rubric, corrected "default model"/"estimated paid" billing language, and explicit Slice 6 completion-gating on the deferred stronger model. Also resolved the paid-tier opt-in storage decision (dedicated `workspace` column, default off). Planning only; superseded by v3 above.
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
