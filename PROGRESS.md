# Outpost Progress and State

Read this at the start of every session. It is a current snapshot, not a chronological log. Detailed history lives in `docs/history/`; completed plans live in `docs/plans/completed/`.

## Current state

Slices 0–4 are implemented and committed. The retained baseline is **171 passing tests** via:

```powershell
python -m unittest discover -s tests
```

Slice 5 — creator sources and demo mode — is next. Its planning-only document
exists at `docs/plans/SLICE_5_PLAN.md` and includes the owner-approved review
corrections. Slice 5 implementation has not been approved or started.

## Implemented product

- **Foundation and workspaces:** FastAPI, SQLite, server-rendered HTML, light/dark tokenized design, workspace creation/switching through a cookie, and workspace-scoped settings with masked keys.
- **B2B discovery:** free-text campaign intake becomes a validated `Brief`; Apollo is the paid B2B source; seeded companies provide the zero-key and provider-failure fallback. Every source returns the shared `SourceResult` contract and preserves the real attempted-source status and sanitized reason.
- **Fit scoring:** Gemini scores a discovered batch in one structured call. Every citation is grounded against normalized provider evidence. Missing, invalid, duplicated, or ungrounded assessments fall back to a deterministic grounded heuristic; no score is persisted without at least one grounded reason.
- **Drafting and approvals:** Gemini or the deterministic zero-key heuristic produces evidence-referencing drafts. Model drafts pass a runtime grounding gate. A human can save, approve, or reject; approving commits the textarea's current normalized text.
- **Pipeline:** Approved targets enter queued/contacted/replied/live/declined state transitions. Illegal transitions are controlled conflicts, same-stage requests are no-ops, and stage changes require an approved draft.
- **Audit:** Intake, discovery, scoring, draft, approval, rejection, and stage actions are recorded. Slice 4 mutations commit their required audit row atomically with the state change.

## Current data model

`app/db.py` creates these SQLite tables idempotently without resetting local data:

- `workspace`
- `workspace_setting`
- `campaign`
- `target`
- `audit`
- `draft`

Every tenant-facing database function requires `workspace_id`. `draft` has a partial unique index allowing at most one non-rejected draft per target. `cost_tokens` exists on `draft` for Slice 6 and is not populated yet.

## Active implementation guarantees

- Workspace keys and records never cross tenant boundaries.
- Provider failures degrade to typed, audited fallback behavior without leaking credentials.
- Gemini structured output uses provider-side JSON schema plus local Pydantic validation and one retry.
- Scoring reads only normalized evidence and persists scores/targets atomically.
- A rejected Gemini credential is not retried redundantly by later steps in the same request.
- Draft bodies share one 20–1500 character validator and normalize CRLF/CR to LF.
- Conditional draft updates prevent concurrent terminal actions from both succeeding.
- `set_target_stage` uses `BEGIN IMMEDIATE` so its `"old -> new"` audit detail is authoritative under concurrency.
- Save → revert to original → approve clears stale `edited_body`; Pipeline always shows exactly what the human approved.
- Nothing sends or posts automatically.

Implementation details and rationale are indexed in `DECISIONS.md`; retained behavior is authoritative in code and tests.

## Provider verification

- **Gemini:** A DB-write-free live `draft_outreach` call succeeded on 2026-07-31 with `DraftStatus.LLM_OK`, `model_used == "gemini-3.6-flash"`, no fallback, and no error. The approved verification workspace is `Slice 3 Verify` (id `5`); follow `CLAUDE.md` without inspecting or copying the key.
- **Apollo:** The owner's plan-limited key was live-verified to return the expected insufficient-plan response, which maps to seeded fallback with a truthful warning.
- **Zero-key mode:** Intake, seed discovery, heuristic scoring, grounded heuristic drafting, approval, and pipeline flows have been verified end to end.

## Known limitations

- `add_draft` identifies the active-draft unique-index race through SQLite's error-message columns because the driver exposes no constraint-specific exception.
- SQLite uses its default five-second lock timeout; lock exhaustion is not specially translated.
- Draft grounding uses normalized substring matching for prose, so a short evidence value can match incidentally.
- Creator actor inputs, current pricing, YouTube quota behavior, and provider
  transport controls have been researched against official documentation for
  the Slice 5 plan. Live provider failure mappings remain explicit assumptions
  except for safely reproducible cases; the plan requires mocked retained tests
  and forbids inducing them by exhausting quota or creating billing errors.

## Slice checklist

- [x] Slice 0: Foundation
- [x] Slice 1: Workspaces and BYO-key settings
- [x] Slice 2: B2B discovery
- [x] Slice 3: Fit scoring with grounded citations
- [x] Slice 4: Drafting, approval queue, and pipeline
- [ ] Slice 5: Creator sources and demo mode
- [ ] Slice 6: Evaluation and cost-aware routing

## Next action: approve the corrected Slice 5 plan

Before Slice 5 implementation begins:

1. Owner confirms no planning corrections remain outstanding.
2. Owner explicitly approves implementation and confirms the required model switch.
3. Implementation follows `docs/plans/SLICE_5_PLAN.md`, beginning with only
   the safe live checks permitted by §7.2; it must not intentionally reproduce
   quota, rate-limit, billing, plan, or paid-run failures.
4. Preserve the shared Source/`SourceResult` and normalized-evidence contracts
   and the complete zero-key demo path.

## Relevant references

- Product scope and Slice 5 requirements: `SPEC.md`
- Active constraints: `DECISIONS.md`
- Current collaboration handoff: `collaboration.md`
- Completed implementation plans:
  - `docs/plans/completed/SLICE_2_PLAN.md`
  - `docs/plans/completed/SLICE_3_PLAN.md`
  - `docs/plans/completed/SLICE_4_PLAN.md`
- Detailed decision and collaboration history:
  - `docs/history/DECISIONS_LOG.md`
  - `docs/history/COLLABORATION_LOG.md`

## Writeup backlog

Strongest portfolio topics remain: human approval before sending, cost-aware routing with real numbers, and a source-agnostic discovery engine.
