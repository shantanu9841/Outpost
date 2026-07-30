# Outpost Progress and State

Read this at the start of every session. Update it at the end of every slice.

## Current state
Slices 0–2 done and committed. Two tables (`workspace`, `workspace_setting`) live in
`app/db.py`, both created idempotently on startup. The active workspace is tracked
in a plain cookie, resolved per-request by the `get_current_workspace` FastAPI
dependency — every route that touches tenant data depends on it and every db.py
function takes `workspace_id` as a required parameter (forgetting it is a
TypeError, not a silent leak). A workspace can be created (`/workspaces/new`) and
switched via a dropdown in the side rail. A settings page (`/settings`) lets the
owner paste and save youtube/apify/apollo/gemini keys per workspace; saved keys
display masked (`••••` + last 4 chars) and can be removed.

Slice 2 adds campaign intake and B2B discovery. `/campaigns/new` takes a free-text
"what are you promoting" description; `app/agent/intake.py` parses it into a
validated `Brief` via Gemini when a key is present, or a deterministic heuristic
(including word-boundary country-name extraction) when not — either path always
returns a usable brief. `app/sources/` implements the Source interface: every
source's `search()` returns one shared `SourceResult` (candidates, status,
source_attempted, source_used, sanitized reason) and never raises past its own
boundary. `app/sources/apollo.py` calls Apollo's real company-search API with the
workspace's own key; `app/sources/__init__.py`'s `discover()` is the only place
that decides to fall back to seeded data (`seeds/companies.json`, 10 companies
across US/UK/Germany) and always preserves *why* — no key, invalid key,
insufficient plan, or network error — so campaign-detail always shows both the
fallback data and the reason. Every intake and discovery outcome is written to a
new `audit` table (with `campaign_id` from the start) via explicit status→action
maps in `app/audit_banners.py`, and rendered back as info/warning banners on
`/campaigns/{id}` using only existing design tokens. The `llm` workspace-setting
key was renamed to `gemini` (idempotent migration, existing rows preserved).

Verified end to end against the real Apollo and Gemini APIs (not just seed data):
confirmed the owner's real, plan-limited Apollo key (workspace "Demo Wellness
Co") returns a 403 that maps to `INSUFFICIENT_PLAN` with a correct fallback and
warning banner — this is the exact regression that motivated the corrected Slice
2 plan — confirmed a fresh workspace with no keys shows 6 US seed rows with two
info banners, confirmed a brief mentioning "UK and Germany" with no Gemini key
extracts both countries and the seed filter returns exactly the 4 non-US rows,
confirmed invalid-credential paths for both Apollo (401) and Gemini via a
temporary, DB-write-free script (deleted afterward, per the plan), confirmed
audit rows and campaign/target rows stay correctly scoped to their own workspace
(Alpha and Beta show zero campaigns), and confirmed banner colors and the
`.banners` gap resolve from `--info`/`--warning`/`--space-4` via computed-style
checks in both light and dark themes. Screenshots were not available in this
session's headless browser tooling; computed-style verification (the plan's
preferred method) fully substituted. One new dependency added: `httpx` (used for
both the Apollo and Gemini REST calls — logged in DECISIONS.md).

**Slice 2 hardening pass** (branch `codex/sde-1-slice-2-hardening`, done jointly
by SDE 1 and SDE 2) closed eight gaps found before Slice 3 could be trusted to
build on top of Slice 2's error handling: `app/llm.py` no longer leaks a raw
`JSONDecodeError`/`KeyError`/`IndexError` when Gemini returns HTTP 200 with a
malformed, empty, or textless body — every such case now becomes a sanitized
`LLMError(ERROR)` and `intake.parse_brief` degrades to the heuristic Brief with
`GEMINI_ERROR`; the request now also sends `generationConfig.responseJsonSchema`
(derived from `model_json_schema()`) so Gemini enforces structure server-side in
addition to local Pydantic validation; `SourceStatus` grew `RATE_LIMITED`,
`PROVIDER_ERROR`, and `SEED_ERROR` so a 429 or 5xx from Apollo is no longer
misclassified as a bad key, with banner copy that tells the owner to wait or
that it's Apollo's side, not theirs; both `ApolloSource` and `SeedSource` now
hold to a genuine "never raises" contract (malformed 200 payloads, missing/
invalid/misshaped seed files, and invalid UTF-8 all become typed failures), and
`discover()` no longer claims seed data was shown if the seed fallback itself
fails; provider error messages are now redacted for an echoed credential before
they ever reach the UI or audit trail; `POST /campaigns` validates `target_type`
against the shared `TargetType` literal (422 on garbage) and rejects empty/
whitespace `promoting_what` (422) instead of risking a 500; and the Settings
page's Gemini hint now accurately describes the GEMINI_API_KEY/demo-heuristic
fallback instead of overstating a "free tier." A maintained `tests/
test_slice2_hardening.py` (unittest, mocked httpx, temp SQLite, 32 tests) now
guards all of this — no more disposable one-off scripts for this kind of check.
Live-verified with a freshly rotated Gemini key pasted through Settings (the
key posted earlier in chat was treated as compromised and never used): the live
call surfaced that `gemini-2.5-flash` is no longer available to new users, so
— after stopping to ask the owner, per the hardening instructions — `GEMINI_MODEL`
was updated to `gemini-3.6-flash` (current stable per ai.google.dev), re-verified
live to produce a correctly-parsed Brief with `intake.llm_ok` recorded, the key
masked in Settings, and no key value in console output, audit `detail`, tracked
files, or git history.

Slice 3 adds fit-scoring with grounded citations. `app/models.py` gained
`FitReason` (`reason`/`evidence_key`/`evidence_value`, all non-blank),
`FitAssessment` (0-100 `fit_score`, >=1 reason), and `FitBatch` (a list of
per-target assessments keyed by `target_index`) — the schema the whole slice
is built around. Both sources gained a `normalize_evidence()` mapping their
own raw fields (Apollo's `estimated_num_employees`, seed's `employees`) to
one shared shape (`name`/`industry`/`employees`/`country`/`domain`);
`Source.evidence()` now returns that normalized shape, and a new
`sources.evidence_for(source_used, candidate)` dispatches to the right
normalizer. `app/agent/scoring.py`'s `score_batch()` asks Gemini to score
every discovered target in **one** structured call (bounded latency, and a
rejected credential is a single 401/403, never a per-target retry loop);
every returned citation is checked with `_is_grounded()` against that
target's real evidence (key present, value not `None`/blank, value
matching) before being trusted, and any target whose assessment is missing,
duplicated away, out-of-range, or has even one ungrounded reason falls back
to a deterministic heuristic (exact weights: industry-overlap 0-60,
size-band 0-25, country-match 0-15) that is grounded by construction. The
aggregate outcome (`ScoreStatus`: `LLM_OK`/`PARTIAL_HEURISTIC`/
`NO_GEMINI_KEY`/`INVALID_GEMINI_KEY`/`GEMINI_ERROR`) is reported honestly,
never assumed uniform. `create_campaign` extends Slice 2's sequence with an
explicit zero-target branch (audits `scoring.skipped_no_targets`, no
scoring call) and, when there are targets, persists them together with
their fit scores in one transaction via `db.add_scored_targets` (which
guards `len(candidates) == len(scores)` before opening any connection,
raising and writing zero rows on a mismatch). A third `SCORING_MAP` in
`audit_banners.py` renders the outcome as a third stacked banner on
`/campaigns/{id}`. The target table (Slice 2's schema already had
`fit_score`/`fit_reasons_json`) needed no migration. The detail table
gained a right-aligned, mono **Fit** column colored by design.md's band
(`fit--high`/`fit--mid`/`fit--low`), and each scored row can expand a
`reasons-row` via a real `<button>` caret with `aria-expanded` (native
keyboard support, no extra JS needed for Enter/Space). One deliberately
weak seed company (`Lakeside Software Studio`, 12 employees, an unrelated
industry) was added to `seeds/companies.json`, changing the US seed count
from 6 to 7; the Slice 2 test asserting exactly 6 US targets was updated to
read the expected count from the seed file itself rather than a literal, so
it won't need another manual update the next time a seed row changes.

Two retained test modules now guard this (57 tests total, `python -m
unittest discover -s tests`): `tests/test_slice3_scoring.py` (25 tests —
schema shape, grounding including the `None`/blank-value rejection case,
heuristic anchor scores against a canonical brief, evidence normalization,
batch aggregation for ungrounded/missing/duplicate/out-of-range
`target_index` values, the terminal-credential-failure single-call
guarantee, atomic persistence + the length guard, and the zero-target
branch) and the updated `tests/test_slice2_hardening.py` (32 tests, all
still green). Verified live end-to-end in a scratch workspace ("Slice 3
Verify"): a zero-key campaign correctly heuristic-scored all 7 US seed
targets with the weak company lowest (20) and the other six all `fit--low`
(this run's brief text didn't happen to cross 70, which is expected — the
heuristic's exact anchor numbers are pinned to the retained tests' fixed
canonical brief, not to whatever text a live user types); a second campaign
in the same workspace, run against a freshly rotated Gemini key pasted
through Settings (never read by this session — confirmed present only by
`length(key_value)` and `created_at`), produced `scoring.llm_ok` with every
one of the 7 targets LLM-scored and every citation grounded against real
seed fields (no heuristic fallback needed) — confirming Gemini accepts the
new nested `FitBatch` schema, which no mocked test could prove on its own.
Confirmed no credential leakage: browser console was empty, server logs and
`git diff`/`git log --all -p` had no `AIza`-prefixed strings (one hit was
pre-existing documentation text from the Slice 2 collaboration entry, not a
real key), and Settings shows only the masked placeholder. Computed-style
checks confirmed `.fit--low` resolves to `--text-3` in both light and dark
themes, and the caret's `aria-expanded`/`hidden` toggle and 90° rotation
were confirmed via its actual click handler. Cross-workspace isolation
reconfirmed directly against `outpost.db` (a different workspace sees none
of the scored campaign's targets or audit rows).

**Slice 3 hardening pass** closed four gaps found after a route-level
diagnostic, before Slice 4 could build on top of scoring's error handling: a
campaign with an invalid Gemini key was making two live Gemini calls in one
request (intake's, then a redundant second one from scoring re-asking a
credential already known rejected) — `scoring.score_batch()` now accepts
`known_invalid_key_reason` and skips its own call entirely when intake
already established the terminal failure; a malformed/empty Apollo
organization object could produce a fabricated `name: "this target"`
citation that didn't match the real (missing) evidence value — Apollo's
`normalize_evidence` now defaults `name` the same way `Candidate.name`
already did, and the heuristic's zero-evidence fallback now cites the real
value or emits zero reasons, never a placeholder; the industry-overlap
heuristic used exact token matching, so a natural brief like "US
distributors for magnesium" scored obvious distributors as a poor fit
purely because "distributors" and "distribution" are different word forms
— a minimal suffix-stemmer now unifies them, and the no-overlap explanation
no longer claims to evaluate `brief.product` (which it never reads); and an
evidence employee count arriving as a string (e.g. `"180"`) raised a
`TypeError` against `score_batch`'s own "never raises" contract — a new
`coerce_int()` normalizes numeric evidence fields at the source boundary,
and `_heuristic()` also guards its own arithmetic defensively. 15 new
retained tests (72 total) cover all four, including a route-level test
proving exactly one Gemini HTTP call per request with a rejected key.
Verified the stemming fix reproduces the exact anchor-table scores
unchanged (regression guard) while fixing the demonstrated live-phrase gap
by direct script.

## Slice checklist
- [x] Slice 0: Foundation (scaffold, git, styled shell, theme toggle)
- [x] Slice 1: Workspaces and BYO-key settings
- [x] Slice 2: B2B discovery (Apollo)   [load skill: apollo:prospect, apollo:enrich-lead]
- [x] Slice 3: Fit-scoring with citations
- [ ] Slice 4: Drafting, approval queue, pipeline   [load skill: beautiful-prose, humanizer]
- [ ] Slice 5: Creator sources and demo mode
- [ ] Slice 6: Eval and cost-aware routing

## Session ritual
Start: read PROGRESS.md and DECISIONS.md, confirm which slice is next.
During: plan mode first, build one slice, run it locally, show the output.
End: update this file (done plus next), append any real decision to DECISIONS.md, commit to git.

## Notes and open items
- Confirm the current Apify Instagram and TikTok actor and its pricing before wiring, during Slice 5.
- Confirm YouTube Data API free-quota search covers the creator search we need, during Slice 5.
- Write a custom outreach-voice skill once Slice 4 produces first drafts and there is real output to react to. Not before.

## Writeup backlog (from DECISIONS.md, for later)
Every decision entry is a candidate post. Strongest three for the portfolio: human-approves-every-send, cost-aware routing with real numbers, source-agnostic design.
