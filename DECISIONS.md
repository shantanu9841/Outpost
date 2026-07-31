# Outpost Active Decisions

Read this at the start of every session. It contains only decisions that still constrain future work. Full rationale, rejected alternatives, superseded choices, and chronological entries are preserved in `docs/history/DECISIONS_LOG.md`.

Status meanings:

- **Active:** must be followed unless the owner explicitly changes it.
- **Superseded:** retained only in history; never overrides an active decision.
- **Historical:** describes completed work but imposes no new default reading requirement.

When changing an active decision, stop for owner approval, update this index and the detailed history in the same commit, and add or update retained tests where behavior changes.

## Product and architecture

| Active decision | Constraint |
|---|---|
| One engine, not separate projects | Business and creator discovery share one campaign, source, scoring, drafting, approval, audit, and pipeline engine. |
| Domain-neutral public build | Keep the repository reusable; client-specific data and credentials remain local workspace data. |
| Source-agnostic discovery | Provider modules implement the shared Source interface; routes and downstream agents do not depend on provider-specific payloads. |
| Apollo for B2B | Use Apollo's organization search for business targets, never LinkedIn scraping. |
| Maintained API for creator data | Prefer a maintained paid provider such as an Apify actor over a self-hosted social scraper; Slice 5 must verify the current actor and pricing before choosing. |
| BYO-key and free/demo paths | The owner supplies workspace-scoped credentials. The builder incurs no provider cost, and zero-key workflows remain usable. |
| Cost-aware routing | Slice 6 will route work using measured quality/cost signals; `draft.cost_tokens` is already reserved for this. |
| Human approval before send | Drafting and approval are separate. Nothing transmits automatically; every human/agent action is audited. |
| Local-first stack | Python, FastAPI, SQLite, server-rendered HTML, and light vanilla JavaScript remain the default. |
| Locked design system | `design.md` tokens and components govern UI work; support light and dark themes. |
| Repository artifacts | Implement changes as reviewable files and retained tests, not as paste-only prompts or disposable scripts. |

## Tenancy, credentials, and local state

| Active decision | Constraint |
|---|---|
| Explicit workspace scope | Every tenant database function requires `workspace_id`; no implicit global tenant or unscoped read. |
| Cookie-based active workspace | A plain workspace cookie selects local workspace state; accounts/authentication remain out of current scope. |
| Workspace-scoped settings | Keys belong to one workspace, are masked in UI, and cannot be silently copied to another workspace. |
| Credential-safe errors | Provider reasons are sanitized before audit or display and must redact echoed credentials. Never log raw keys. |
| Preserve local data | Schema initialization is idempotent. Never reset or delete `outpost.db`, seeds, settings, or scratch workspaces without owner approval. |

## Provider and discovery contracts

| Active decision | Constraint |
|---|---|
| Shared `SourceResult` | Every source returns candidates plus attempted/used source, typed status, and sanitized reason; providers do not raise past their boundary. |
| Honest fallback status | `discover()` may substitute seed data but preserves why the real source failed. It never claims fallback data was shown if seed loading also fails. |
| Typed provider failures | Invalid credentials, insufficient plan, rate limits, provider errors, network errors, and seed errors remain distinguishable. |
| Structured Gemini output | Gemini requests include `responseJsonSchema`; responses are also validated locally with Pydantic and one retry. |
| Current Gemini model | Use `gemini-3.6-flash` until a separately approved, live-verified model change is required. |
| Shared HTTP client dependency | `httpx` is the approved external HTTP dependency. `python-multipart` supports form handling; the retained test suite uses the standard-library `unittest`. |
| Evidence normalization boundary | Each provider maps raw data to the canonical evidence shape before scoring. Scoring never reads provider-specific raw fields. |
| Canonical nonblank name | Provider candidate identity and normalized `name` evidence use the same canonicalization; malformed curated seed names fail rather than silently diverge. |

## Intake and scoring

| Active decision | Constraint |
|---|---|
| Explicit intake outcomes | Intake distinguishes LLM success, no key, rejected key, and provider error so audit/fallback behavior remains truthful. |
| One scoring call per batch | Gemini scores all discovered targets in one structured call, never one provider request per target. |
| Grounded citations | A schema-valid score is insufficient: every cited key/value must match normalized evidence for that target. |
| Deterministic grounded fallback | Missing, duplicate, invalid, out-of-range, or ungrounded assessments fall back to a deterministic heuristic. No score is persisted without a grounded reason. |
| Atomic target persistence | Candidates and their scores persist together after a length check; mismatches write nothing. |
| Zero targets are explicit | No-target discovery is an audited no-op and never invokes scoring. |
| Terminal credential reuse | If intake already learned the Gemini key is rejected, scoring skips its own redundant provider call. |
| Defensive numeric evidence | Employee counts are coerced at normalization; NaN, infinity, non-integral floats, and malformed values become unavailable rather than raising or truncating. |
| Industry heuristic normalization | Industry comparison uses the retained minimal stemming and short-token exclusion behavior; anchor scores are protected by tests. |

## Drafting, approval, and pipeline

| Active decision | Constraint |
|---|---|
| Separate state machines | Draft status and target pipeline stage use explicit transition maps enforced in the database, not only the UI. |
| One active draft per target | A partial unique index permits at most one non-rejected draft; re-drafting is allowed after rejection. |
| Grounded LLM drafts | Model drafts cite one stored Slice 3 evidence pair, use its value in the body, and name the recipient when meaningful; failures fall back to the heuristic. |
| Neutral zero-key drafting | The deterministic draft states stored evidence without turning a poor-fit fact into a positive claim. |
| Shared body validation | Model and human bodies share the 20–1500 character validator in `app/models.py`; CRLF/CR normalize to LF. |
| Approve current textarea | Approval atomically commits the normalized submitted body. If it equals the immutable original, stale `edited_body` is cleared; otherwise submitted text becomes `edited_body`. |
| Atomic mutation and audit | Draft creation/edit/approve/reject and stage changes commit their audit row with the mutation or roll back together. |
| Conditional draft transitions | Save, approve, and reject use conditional `UPDATE ... WHERE status IN (...)` plus `rowcount` so concurrent terminal actions cannot both succeed. |
| Locked stage transitions | `set_target_stage` uses `BEGIN IMMEDIATE` before its scoped approved-draft/stage read and holds the reservation through validation, update, truthful `"old -> new"` audit, and commit. |
| Approved-draft pipeline gate | A target cannot change stage until it has a workspace-scoped approved draft; missing, cross-workspace, and not-admitted targets share the non-leaking `NotFound` response. |
| Terminal stages | `live` and `declined` are terminal in the current slice; same-stage requests are no-ops with no audit row. |
| Nothing sends | Approval and `contacted` are stored workflow state only. No outbound messaging integration exists. |

## Schema commitments

- `audit.campaign_id`, `audit.target_id`, and `audit.draft_id` support traceable actions.
- `target.fit_score`, `target.fit_reasons_json`, and `target.stage` are the persisted scoring/pipeline fields.
- `draft` stores original and edited body, status, model, creation time, and future `cost_tokens`.
- New tables and migrations must remain idempotent and preserve existing local rows.

## When to read detailed history

Open `docs/history/DECISIONS_LOG.md` when:

- An active constraint needs to change.
- The rejected alternatives or original evidence matter.
- A completed subsystem regression requires its historical rationale.
- A current plan links to a specific detailed decision.

For completed implementation contracts, also consult the relevant file under `docs/plans/completed/`. Historical wording cannot override this active index, `CLAUDE.md`, `SPEC.md`, or a current owner-approved plan.
