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

- **Owner-approved activity:** Slice 6 (evaluation and cost-aware routing) — **implemented and review-corrected**, per owner-approved plan v4 plus a five-finding owner-directed implementation review. All application code, schema, routing, evaluation, persistence, UI, audit, tenant-isolation, and credential-handling work is complete and committed.
- **Role:** Claude Code / SDE 1, implementer. Executed on Sonnet per the owner's model confirmation.
- **Branch/baseline:** `codex/sde-1-slice-2-hardening`. Implementation baseline was `f052a10` (Slice 6 plan v4, 212 retained tests); the initial implementation commit (`d7f2cc8`) brought the suite to 263; this review-correction pass brings it to 281, clean after this commit.
- **Product state:** Slices 0–5 are complete. Slice 6 is implemented, tested, and review-corrected but **not complete against `SPEC.md` §6** — see the owner-gate below.
- **What shipped (initial implementation, `d7f2cc8`):** `app/agent/eval.py` (new), `app/agent/routing.py` (new), `app/llm.py` (workspace-key-only, header-only `x-goog-api-key` auth, per-attempt `TokenUsage`, `generate_structured_with_usage`), `app/agent/drafting.py` (`BANNED_FILLER_PHRASES`, `usage`/`model` additions), `app/models.py` (`EvalDimension`/`EvalRubric`/`EvalResult`), `app/db.py` (`eval` table, `workspace.paid_tier_enabled`, `draft.cost_breakdown_json`/`estimated_cost_microusd`, atomic `create_draft_with_routing`), `app/audit_banners.py` (eval/routing action maps), `app/main.py` + four templates (routing wiring, eval/cost UI, paid-tier Settings checkbox), and `tests/test_slice6_eval_routing.py` (51 tests). `tests/test_slice4_drafting.py` was mechanically updated (9 tests) to mock `llm.generate_structured_with_usage` instead of the now-internal `llm.generate_structured` — no assertion or scenario changed.
- **What shipped (review-correction pass):** a durable `draft_generation` reservation table plus `db.try_acquire_draft_generation`/`release_draft_generation`, acquired in `main.py`'s `create_draft` before any Gemini call and released in a `finally` block (300s TTL backstop) — closes a real concurrent-spend gap; `routing.route_and_draft` now only promotes an escalated result on `DraftStatus.LLM_OK`, otherwise keeping the default draft/eval and recording the new `routing.escalation_failed` audit action; `routing._escalation_ready()` now requires both `ESCALATION_MODEL` and a verified `Decimal` pricing entry for it; `app/templates/approvals.html`'s cost summary now keys off `cost_summary.draft_count` instead of the pending-drafts queue, and always shows the unknown-cost count when one exists; `SPEC.md`'s stale "falls back to the free Gemini tier" line corrected. 18 new tests in `tests/test_slice6_eval_routing.py`.
- **Preserved contracts:** strict workspace-only keys, header-only Gemini authentication, no-request-only zero accounting, per-attempt usage and retry preservation, independently nullable token/cost aggregates, explicit workspace-scoped paid opt-in, inclusive 85/80 thresholds, fully specified eval rubric and heuristic fallback, atomic draft/eval/cost/audit persistence, tenant isolation, and no paid live verification without owner authorization (none was performed or requested this session).
- **Known limitation/gate:** The stronger-model id and its pricing remain owner-gated and unset (`ESCALATION_MODEL = None`). Slice 6's routing plumbing is fully implemented and mocked-tested but dormant until the owner approves a specific model id and it passes the same kind of safe verification gate Slice 5 used. See `PROGRESS.md`'s "Owner-gated" section.
- **Next action:** Owner review of the corrected implementation. If/when the owner wants the escalation tier active, approve a specific stronger Gemini model id (and its verified pricing) so it can be safely, boundedly verified per the completed plan's §6.

## Recent activity

- **Slice 6 implementation review corrected: five findings.** Claude Code /
  SDE 1 corrected five owner-identified review findings on top of the
  initial Slice 6 implementation: (1) a durable, workspace-scoped
  `draft_generation` reservation now prevents two concurrent draft
  requests for the same target from both incurring provider spend — the
  reservation is acquired before any Gemini call, released in a `finally`
  block, and backstopped by a 300s TTL; (2) `routing.route_and_draft` no
  longer mislabels a failed/ungrounded escalated draft as `"escalated"` —
  it keeps the valid default draft/eval and records the new
  `routing.escalation_failed` audit action instead, and skips a wasted
  escalated-eval call; (3) escalation now requires a verified pricing
  entry for `ESCALATION_MODEL`, not just the model id, via
  `routing._escalation_ready()`; (4) the Approvals cost summary no longer
  disappears when the pending queue is empty, and the unknown-cost
  "excluded" count no longer disappears when there are zero known-cost
  drafts; (5) `SPEC.md`'s stale "falls back to the free Gemini tier"
  description of `app/llm.py` is corrected. 18 new tests; 281/281 total
  pass. `ESCALATION_MODEL` remains `None`; no live/paid provider call was
  made. See the current handoff above for the full file list.
- **Slice 6 implemented: evaluation and cost-aware routing.** Claude Code /
  SDE 1 implemented `docs/plans/completed/SLICE_6_PLAN.md` v4 end to end on
  Sonnet: `app/agent/eval.py` and `app/agent/routing.py` (new), workspace-
  key-only header-authenticated Gemini calls with per-attempt `TokenUsage`
  accounting in `app/llm.py`, `Decimal`-priced/`ROUND_HALF_UP`-rounded cost
  aggregation, terminal invalid-key handling across all four model-backed
  routing stages, an atomic `db.create_draft_with_routing`, and Approvals/
  Pipeline/campaign-detail/Settings UI. 263/263 tests pass (212 baseline +
  51 new); `ESCALATION_MODEL` stays owner-gated at `None`. See the current
  handoff above for the full file list and known limitations.
- **Slice 6 plan corrected (v4):** applied the owner-authorized final review set against v3: invalid credentials are terminal after every Gemini-backed routing stage; official `gemini-3.6-flash` paid list pricing is recorded as verified on 2026-08-01; and cost estimation uses string-constructed `Decimal` rates, exact accumulation, and one final `ROUND_HALF_UP`. Planning only; no Slice 6 implementation began.
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
