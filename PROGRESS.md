# Outpost Progress and State

Read this at the start of every session. It is a current snapshot, not a chronological log. Detailed history lives in `docs/history/`; completed plans live in `docs/plans/completed/`.

## Current state

Slices 0–5 are implemented and committed. The retained baseline is **206 passing tests** via:

```powershell
python -m unittest discover -s tests
```

(171 pre-Slice-5 tests, unchanged, plus 35 new tests in
`tests/test_slice5_creators.py`.)

## Implemented product

- **Foundation and workspaces:** FastAPI, SQLite, server-rendered HTML, light/dark tokenized design, workspace creation/switching through a cookie, and workspace-scoped settings with masked keys.
- **B2B discovery:** free-text campaign intake becomes a validated `Brief`; Apollo is the paid B2B source; seeded companies provide the zero-key and provider-failure fallback. Every source returns the shared `SourceResult` contract and preserves the real attempted-source status and sanitized reason.
- **Creator discovery:** Apify (Instagram + TikTok, merged with partial-success and deterministic failure precedence) when configured, else YouTube when configured, else creator seed — a deterministic priority, never an auto-aggregation. Both providers authenticate via a request header (never a query-param key/token); Apify runs are started, bounded-polled, and fetched with named timeout/item/cost caps, never `run-sync`. Creator seed data (`seeds/creators.json`) spans strong/partial/geographic-mismatch/weak/irrelevant examples so heuristic ranking discrimination is visible with zero keys.
- **Fit scoring:** Gemini scores a discovered batch in one structured call, with a target-type-aware prompt (creator vs company). Every citation is grounded against normalized provider evidence. Missing, invalid, duplicated, or ungrounded assessments fall back to a deterministic grounded heuristic (target-type-aware: business's industry/size/country components are unchanged; creator adds niche/followers/country components with exact follower bands). No score is persisted without at least one grounded reason.
- **Drafting and approvals:** Gemini or the deterministic zero-key heuristic produces evidence-referencing drafts, for both business and creator targets. Model drafts pass a runtime grounding gate. A human can save, approve, or reject; approving commits the textarea's current normalized text.
- **Pipeline:** Approved targets enter queued/contacted/replied/live/declined state transitions. Illegal transitions are controlled conflicts, same-stage requests are no-ops, and stage changes require an approved draft.
- **Audit:** Intake, discovery (business and creator, namespaced separately so no action key collides), scoring, draft, approval, rejection, and stage actions are recorded. Slice 4 mutations commit their required audit row atomically with the state change.

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
- Every creator source (YouTube, Apify's Instagram/TikTok actors, creator seed) sets a controlled `_outpost_platform` marker on `Candidate.raw` from its own constant, never an untrusted provider field; `target.source` stays the source-level value (`youtube`/`apify`/`seed`) and `campaign_detail` renders the platform label from the persisted marker.
- `evidence_for(source_used, target_type, candidate)` dispatches seed's business/creator normalizers by `target_type` so the two shapes (business vs creator) can never collide under `source_used == "seed"`.
- Business and creator discovery audit actions are namespaced so no key collides (`discovery.apollo_ok` vs `discovery.apify_ok`/`discovery.youtube_ok`; `discovery.seed_error` vs `discovery.creator_seed_error`, etc.).

Implementation details and rationale are indexed in `DECISIONS.md`; retained behavior is authoritative in code and tests.

## Provider verification

- **Gemini:** A DB-write-free live `draft_outreach` call succeeded on 2026-07-31 with `DraftStatus.LLM_OK`, `model_used == "gemini-3.6-flash"`, no fallback, and no error. The approved verification workspace is `Slice 3 Verify` (id `5`); follow `CLAUDE.md` without inspecting or copying the key.
- **Apollo:** The owner's plan-limited key was live-verified to return the expected insufficient-plan response, which maps to seeded fallback with a truthful warning.
- **Apify/YouTube:** Live-verified 2026-07-31 with synthetic invalid credentials only (no owner key was authorized this session): Apify's start-run returns `401`/`user-or-token-not-found` for a bogus Bearer token; YouTube's `search.list` returns `400`/`INVALID_ARGUMENT`/"API key not valid" for a bogus `X-goog-api-key` header. Both confirm the §5.4 `INVALID_KEY` mapping and the header-auth transport (no credential-bearing URL). The owner-authorized bounded happy-path leg of §7.2 was not run — no `youtube`/`apify` workspace key was made available this session — so a full live creator discovery run remains unverified; the zero-key seed path and the mocked test suite (`tests/test_slice5_creators.py`) are the primary coverage.
- **Zero-key mode:** Intake, seed discovery (business and creator), heuristic scoring (business and creator), grounded heuristic drafting, approval, and pipeline flows have been verified end to end, including through a live browser session (see `docs/history/COLLABORATION_LOG.md`).

## Known limitations

- `add_draft` identifies the active-draft unique-index race through SQLite's error-message columns because the driver exposes no constraint-specific exception.
- SQLite uses its default five-second lock timeout; lock exhaustion is not specially translated.
- Draft grounding uses normalized substring matching for prose, so a short evidence value can match incidentally.
- Apify/YouTube HTTP-status → typed-status mappings beyond the confirmed
  `INVALID_KEY` case (insufficient-plan, rate-limit, provider-error,
  run-lifecycle terminal states) remain explicit assumptions grounded in
  official documentation and covered by mocked retained tests, per
  `docs/plans/completed/SLICE_5_PLAN.md` §5.4/§9 — never deliberately
  reproduced live (quota/billing/plan failures are unsafe to induce).
- Apify/TikTok's exact output field names (`fans` vs `followers`, `nickname`
  vs `nickName`) are taken from official schemas and tolerated defensively
  (a missing field becomes `None`, never a crash); unconfirmed against a real
  dataset item.
- The creator follower bands (10k–500k strong, etc.) are a demo-mode
  heuristic choice, not a calibrated model.
- No live end-to-end creator discovery run (Apify or YouTube) has been
  performed — it requires an owner-provided key, which was not available
  this session.

## Slice checklist

- [x] Slice 0: Foundation
- [x] Slice 1: Workspaces and BYO-key settings
- [x] Slice 2: B2B discovery
- [x] Slice 3: Fit scoring with grounded citations
- [x] Slice 4: Drafting, approval queue, and pipeline
- [x] Slice 5: Creator sources and demo mode
- [ ] Slice 6: Evaluation and cost-aware routing

## Next action: Slice 6 (evaluation and cost-aware routing)

Per `SPEC.md` §6's Slice 6 and this file's Build discipline: recommend a
model, use plan mode, and confirm the plan against `SPEC.md` before writing
any code. If the owner wants a live creator discovery run first, that only
needs a `youtube` and/or `apify` key pasted into a workspace's Settings —
no code change required.

## Relevant references

- Product scope and Slice 6 requirements: `SPEC.md`
- Active constraints: `DECISIONS.md`
- Current collaboration handoff: `collaboration.md`
- Completed implementation plans:
  - `docs/plans/completed/SLICE_2_PLAN.md`
  - `docs/plans/completed/SLICE_3_PLAN.md`
  - `docs/plans/completed/SLICE_4_PLAN.md`
  - `docs/plans/completed/SLICE_5_PLAN.md`
- Detailed decision and collaboration history:
  - `docs/history/DECISIONS_LOG.md`
  - `docs/history/COLLABORATION_LOG.md`

## Writeup backlog

Strongest portfolio topics remain: human approval before sending, cost-aware routing with real numbers, and a source-agnostic discovery engine.
