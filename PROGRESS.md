# Outpost Progress and State

Read this at the start of every session. It is a current snapshot, not a chronological log. Detailed history lives in `docs/history/`; completed plans live in `docs/plans/completed/`.

## Current state

Slices 0–5 are implemented and committed. Slice 6 (evaluation and
cost-aware routing) is implemented, tested, and committed, but is **not**
marked complete against `SPEC.md` §6 — the owner-gated stronger model
(`ESCALATION_MODEL`) remains unset; see "Owner-gated: Slice 6 stronger
model" below. The retained baseline is **263 passing tests** via:

```powershell
python -m unittest discover -s tests
```

(212 pre-Slice-6 tests — 9 updated in `tests/test_slice4_drafting.py` to
mock `llm.generate_structured_with_usage` instead of the now-internal
`llm.generate_structured`, since `app/agent/drafting.py` had to switch call
targets to capture per-attempt usage; every existing assertion/scenario is
unchanged — plus 51 new tests in `tests/test_slice6_eval_routing.py`.)

## Implemented product

- **Foundation and workspaces:** FastAPI, SQLite, server-rendered HTML, light/dark tokenized design, workspace creation/switching through a cookie, and workspace-scoped settings with masked keys.
- **B2B discovery:** free-text campaign intake becomes a validated `Brief`; Apollo is the paid B2B source; seeded companies provide the zero-key and provider-failure fallback. Every source returns the shared `SourceResult` contract and preserves the real attempted-source status and sanitized reason.
- **Creator discovery:** Apify (Instagram + TikTok, merged with partial-success and deterministic failure precedence) when configured, else YouTube when configured, else creator seed — a deterministic priority, never an auto-aggregation. Both providers authenticate via a request header (never a query-param key/token); Apify runs are started, strictly wall-clock-bounded while polling, and fetched with named timeout/item/cost caps, never `run-sync`. TikTok normalization follows the actor's documented nested `authorMeta` profile shape with defensive legacy aliases; malformed YouTube success payloads are provider errors rather than false empty successes. Creator seed data (`seeds/creators.json`) spans strong/partial/geographic-mismatch/weak/irrelevant examples so heuristic ranking discrimination is visible with zero keys.
- **Fit scoring:** Gemini scores a discovered batch in one structured call, with a target-type-aware prompt (creator vs company). Every citation is grounded against normalized provider evidence. Missing, invalid, duplicated, or ungrounded assessments fall back to a deterministic grounded heuristic (target-type-aware: business's industry/size/country components are unchanged; creator adds niche/followers/country components with exact follower bands). No score is persisted without at least one grounded reason.
- **Drafting and approvals:** Gemini or the deterministic zero-key heuristic produces evidence-referencing drafts, for both business and creator targets. Model drafts pass a runtime grounding gate. A human can save, approve, or reject; approving commits the textarea's current normalized text.
- **Pipeline:** Approved targets enter queued/contacted/replied/live/declined state transitions. Illegal transitions are controlled conflicts, same-stage requests are no-ops, and stage changes require an approved draft.
- **Audit:** Intake, discovery (business and creator, namespaced separately so no action key collides), scoring, draft, approval, rejection, and stage actions are recorded. Slice 4 mutations commit their required audit row atomically with the state change.
- **Evaluation and cost-aware routing (Slice 6):** every drafted outreach is scored against a fully-specified four-dimension rubric (personalization, specificity, non-genericness, clear ask) — an LLM judge when a Gemini key is present, else a deterministic heuristic that produces the identical shape. `app/agent/routing.py` drafts with the default model (`gemini-3.6-flash`) or the zero-key heuristic, and escalates to a stronger paid tier only when the workspace's own key, an explicit `paid_tier_enabled` opt-in, and a high fit score (`>= 85`) all hold — escalation is fully implemented and tested but dormant (`ESCALATION_MODEL = None`) until the owner approves a specific stronger model id. An `INVALID_GEMINI_KEY` outcome at any of the four model-backed stages (default draft, default eval, escalated draft, escalated eval) is terminal for the rest of that outreach, preserving every usage entry already collected. Every issued Gemini HTTP attempt — success or failure — produces one `TokenUsage` record; `cost_tokens`/`estimated_cost_microusd` are `NULL` (unknown) whenever any issued attempt's usage or pricing is unreadable, and `0` (known) only when no Gemini request was ever issued. Pricing sums each attempt's exact `Decimal` contribution at its own model's rate and rounds once (`ROUND_HALF_UP`) to integer micro-USD; no binary floats, no per-attempt rounding. The Gemini key is sent only via the `x-goog-api-key` header (no query parameter) and there is no `GEMINI_API_KEY` environment fallback anywhere — every LLM workflow is workspace-key-only. Approvals shows model used, an expandable eval-rubric badge, per-outreach cost (or "cost unknown" / "0 tokens (heuristic, no cost)"), and a running average cost-per-outreach; Pipeline and campaign detail show the same figures more lightly.

## Current data model

`app/db.py` creates these SQLite tables idempotently without resetting local data:

- `workspace` — plus an idempotently migrated `paid_tier_enabled` column (default off).
- `workspace_setting`
- `campaign`
- `target`
- `audit`
- `draft` — plus idempotently migrated `cost_breakdown_json` and `estimated_cost_microusd` columns.
- `eval` (Slice 6) — one row per draft (`draft_id UNIQUE`), `rubric_json` + `score`.

Every tenant-facing database function requires `workspace_id`. `draft` has a partial unique index allowing at most one non-rejected draft per target, and `eval` a unique index on `draft_id` allowing at most one eval per draft. `cost_tokens` on `draft` is now populated by `db.create_draft_with_routing`, the one atomic writer of a routed draft's body, cost columns, eval row, and every required audit row.

## Active implementation guarantees

- Workspace keys and records never cross tenant boundaries.
- Provider failures degrade to typed, audited fallback behavior without leaking credentials.
- Successful provider responses are shape-validated: malformed YouTube search payloads and TikTok rows without creator metadata become typed provider errors and can fall back safely instead of persisting empty or synthetic live results.
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
- `app/llm.py` resolves the Gemini key strictly from the workspace's own saved setting — no `GEMINI_API_KEY` environment fallback anywhere, and a key present only in the process environment can never trigger drafting, evaluation, or escalation.
- Every issued Gemini HTTP attempt (success, transport failure, non-2xx, malformed body, or missing `usageMetadata`) produces exactly one `TokenUsage` record via `llm._extract_usage`; only "no request issued at all" (no workspace key) is a genuinely empty usage list.
- `app.agent.routing.route_and_draft` takes `paid_tier_enabled` as an explicit argument and performs no database access of any kind; `main.py`'s `create_draft` resolves the workspace-scoped flag once, before calling it.
- An `INVALID_GEMINI_KEY` outcome at default draft, default eval, escalated draft, or escalated eval is terminal for the rest of that routing operation, while every usage entry already collected is preserved in `cost_breakdown`.
- `db.create_draft_with_routing` commits the draft (with its cost columns), its eval row, and every required audit row (`draft.created`, `eval.scored`, plus a routing-decision row when one applies) in one transaction, or none.
- `db.eval`'s `draft_id UNIQUE` constraint enforces "exactly one eval per draft" at the database level, not only in application code.

Implementation details and rationale are indexed in `DECISIONS.md`; retained behavior is authoritative in code and tests.

## Provider verification

- **Gemini:** A DB-write-free live `draft_outreach` call succeeded on 2026-07-31 with `DraftStatus.LLM_OK`, `model_used == "gemini-3.6-flash"`, no fallback, and no error. The approved verification workspace is `Slice 3 Verify` (id `5`); follow `CLAUDE.md` without inspecting or copying the key.
- **Apollo:** The owner's plan-limited key was live-verified to return the expected insufficient-plan response, which maps to seeded fallback with a truthful warning.
- **Apify/YouTube:** Live-verified 2026-07-31 with synthetic invalid credentials only (no owner key was authorized this session): Apify's start-run returns `401`/`user-or-token-not-found` for a bogus Bearer token; YouTube's `search.list` returns `400`/`INVALID_ARGUMENT`/"API key not valid" for a bogus `X-goog-api-key` header. Both confirm the §5.4 `INVALID_KEY` mapping and the header-auth transport (no credential-bearing URL). The owner-authorized bounded happy-path leg of §7.2 was not run — no `youtube`/`apify` workspace key was made available this session — so a full live creator discovery run remains unverified; the zero-key seed path and the mocked test suite (`tests/test_slice5_creators.py`) are the primary coverage.
- **Zero-key mode:** Intake, seed discovery (business and creator), heuristic scoring (business and creator), grounded heuristic drafting, approval, and pipeline flows have been verified end to end, including through a live browser session (see `docs/history/COLLABORATION_LOG.md`).

## Owner-gated: Slice 6 stronger model

Slice 6's escalation tier (`app/agent/routing.py`) is fully implemented,
mocked-tested, and wired into the UI, but **dormant**: `ESCALATION_MODEL =
None` is the code gate, and `PRICING_USD_PER_MILLION_TOKENS` has no entry
for it. It stays this way — and Slice 6 stays **not complete** against
`SPEC.md` §6's "high-fit targets route to the better model only when a key
exists" — until the owner approves a specific stronger Gemini model id and
that model passes the same kind of safe, bounded live verification Slice 5
used for Apify/YouTube. No paid live verification has been performed or
authorized this session. This is a documentation/completion-tracking state,
not a bug: every acceptance criterion that *can* be verified without that
model (the default-tier path, terminal invalid-key handling, cost
accounting, the eval rubric, tenant isolation, atomicity) is implemented and
passing.

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
- Apify/TikTok's published nested `authorMeta` profile shape is covered by a
  retained provider-shaped test, with documented/legacy aliases tolerated
  defensively. The mapping is still unconfirmed against an owner-authorized
  live dataset item.
- The creator follower bands (10k–500k strong, etc.) are a demo-mode
  heuristic choice, not a calibrated model.
- No live end-to-end creator discovery run (Apify or YouTube) has been
  performed — it requires an owner-provided key, which was not available
  this session.
- No automated test suite covers a real Gemini `usageMetadata` response
  shape live — `tests/test_slice6_eval_routing.py` is fully mocked at the
  `httpx`/`llm` boundary per collaboration.md rule 9's "no paid live
  verification without explicit authorization." The `thoughtsTokenCount`
  derivation rule (`app/llm.py`'s `_derive_thinking`) is this plan's own
  interpretation of safe derivation for tool-free structured-output calls,
  unconfirmed against a real response.
- The eval judge always runs on the default model (`gemini-3.6-flash`),
  never the escalation model, per `docs/plans/completed/SLICE_6_PLAN.md`
  §5.3 — only drafting escalates.
- Re-evaluating a human-edited draft body is out of scope (SPEC.md §4.8):
  eval scores the agent's created draft once, not the human's later edit.

## Slice checklist

- [x] Slice 0: Foundation
- [x] Slice 1: Workspaces and BYO-key settings
- [x] Slice 2: B2B discovery
- [x] Slice 3: Fit scoring with grounded citations
- [x] Slice 4: Drafting, approval queue, and pipeline
- [x] Slice 5: Creator sources and demo mode
- [~] Slice 6: Evaluation and cost-aware routing — implemented, tested, and
  committed; not complete against `SPEC.md` until `ESCALATION_MODEL` is
  owner-approved and safely verified (see "Owner-gated" above).

## Next action: owner review of Slice 6, then the stronger-model gate

Slice 6 is implemented and committed on the default-tier path. The next
action is owner review, and — if/when the owner wants the escalation tier
active — approving a specific stronger Gemini model id so it can be safely
verified per `docs/plans/completed/SLICE_6_PLAN.md` §6's "Safe live
verification." If the owner wants a live creator discovery run instead,
that only needs a `youtube` and/or `apify` key pasted into a workspace's
Settings — no code change required.

## Relevant references

- Product scope: `SPEC.md`
- Active constraints: `DECISIONS.md`
- Current collaboration handoff: `collaboration.md`
- Completed implementation plans:
  - `docs/plans/completed/SLICE_2_PLAN.md`
  - `docs/plans/completed/SLICE_3_PLAN.md`
  - `docs/plans/completed/SLICE_4_PLAN.md`
  - `docs/plans/completed/SLICE_5_PLAN.md`
  - `docs/plans/completed/SLICE_6_PLAN.md` (implementation complete;
    `ESCALATION_MODEL` remains owner-gated — see "Owner-gated" above)
- Detailed decision and collaboration history:
  - `docs/history/DECISIONS_LOG.md`
  - `docs/history/COLLABORATION_LOG.md`

## Writeup backlog

Strongest portfolio topics remain: human approval before sending, cost-aware routing with real numbers, and a source-agnostic discovery engine.
