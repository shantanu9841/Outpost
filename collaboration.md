# Outpost Collaboration Guide

This file is the operational record for work performed across different SDEs
or coding sessions. It complements, but does not replace:

- `CLAUDE.md` for permanent build rules.
- `SPEC.md` for scope and build order.
- `DECISIONS.md` for architectural and product decisions.
- `PROGRESS.md` for current slice status.

## Collaboration rules

1. Only one SDE may implement a slice at a time. Another SDE may review or
   plan, but must not edit the same branch or working tree concurrently.
2. Every session begins by reading `CLAUDE.md`, `PROGRESS.md`, `DECISIONS.md`,
   `SPEC.md`, `design.md`, and `collaboration.md`.
3. Before editing, inspect the current branch, latest commit, and working-tree
   status. Never assume uncommitted files belong to the current session.
4. SDE 1 creates the initial plan for each slice and may create or edit the
   applicable `SLICE.md` or numbered slice-plan file.
5. SDE 2 is both an implementer and reviewer. SDE 2 may review the existing
   slice plan and propose corrections, but may edit that plan only after the
   owner explicitly approves the proposed changes.
6. No slice implementation begins while plan changes are outstanding. Once the
   owner has approved the plan and confirmed that no further changes are
   required, SDE 2 may implement it. SDE 1 may also implement or review work;
   both SDEs have implementer and reviewer roles.
7. Only one SDE may actively implement a slice in a working tree at a time.
   Agents must not quietly change approved architecture during implementation.
   Any necessary deviation from the approved slice plan must stop for owner
   approval.
8. If implementation of a slice stops before completion, the active SDE must
   update the collaboration log before handing off. After that handoff, either
   SDE may resume the incomplete slice from the documented state.
9. An incomplete-slice handoff must record:
   - Current branch and latest commit.
   - Current slice and approved plan.
   - Uncommitted files, if any.
   - Verification already completed.
   - The last known working state.
   - Remaining work, known risks, and the exact next action.
10. Never delete, reset, overwrite, or absorb another SDE's uncommitted work
   without the owner's approval.
11. When transferring between environments, use committed repository files as
   the source of truth, not chat memory.
12. Never record API keys, credentials, complete secret values, or test secrets
    in tracked files or logs.
13. Verification must be proportional to risk. Tenant isolation and
    fallback/error behavior require UI checks, database checks, and audit-log
    inspection.
14. Prefer text-based and computed-style verification. Take at most two final
    screenshots per slice unless the owner requests more.
15. Temporary verification scripts must not become production dependencies.
    They must either be intentionally retained as tests or removed before the
    slice commit.
16. Every commit must include a new collaboration-log entry summarizing:
    - Date and contributor/environment.
    - Slice and scope.
    - Changes or corrections included.
    - Files or areas affected.
    - Verification performed.
    - Known limitations.
    - Next action.
17. Write the collaboration entry immediately before its corresponding commit
    so it is included in that commit. Recording the resulting hash inside the
    same entry is impossible without changing the hash; the hash remains
    available through Git history and is reported to the owner after the
    commit.
18. Architectural and product decisions still go in `DECISIONS.md`. Slice
    completion and next steps still go in `PROGRESS.md`. `collaboration.md`
    records who changed what, why, and how it was verified.
19. A slice is not complete until required documentation is updated,
    verification passes, and the working tree is clean after commit.

## Collaboration log format

```markdown
## YYYY-MM-DD — Short description

- Contributor/environment:
- Slice:
- Role: Planner / Reviewer / Implementer
- Implementation status: Not started / Incomplete / Complete
- Changes and corrections:
- Files or areas affected:
- Verification:
- Last known working state:
- Known limitations:
- Next action:
```

## Collaboration log

## 2026-07-30 — Collaboration protocol established

- Contributor/environment: Codex desktop
- Slice: Pre-execution coordination for Slice 2
- Role: Reviewer
- Changes and corrections: Added the approved rules for coordinating work
  across SDEs and recording every commit.
- Files or areas affected: `collaboration.md` and the collaboration section in
  `CLAUDE.md`.
- Verification: Documentation diff reviewed; no application code changed.
- Known limitations: The pending Slice 2 plan corrections have not been
  applied or approved for implementation.
- Next action: Obtain owner approval before correcting the Slice 2 plan or
  editing Slice 2 code.

## 2026-07-30 — SDE roles and incomplete-slice handoff clarified

- Contributor/environment: SDE 2 / Codex desktop
- Slice: Collaboration rules for all slices
- Role: Reviewer
- Implementation status: Not started
- Changes and corrections: Recorded that SDE 1 owns the initial slice plan,
  SDE 2 may edit that plan only after owner approval, both SDEs may review and
  implement, and either SDE may resume an incomplete slice after a documented
  handoff.
- Files or areas affected: `collaboration.md` only.
- Verification: Reviewed the collaboration rules and log template for the four
  owner-specified role and handoff requirements.
- Last known working state: No Slice 2 implementation was started or changed.
- Known limitations: The Slice 2 plan corrections remain pending.
- Next action: Wait for owner direction on the Slice 2 plan review and
  implementation sequence.

## 2026-07-30 — Slice 2 plan corrected and committed as SLICE_2_PLAN.md

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 2 (B2B discovery via Apollo) — planning only
- Role: Planner
- Implementation status: Not started
- Changes and corrections: Created `SLICE_2_PLAN.md` on `main` from the
  complete Slice 2 Plan v2, incorporating all twelve owner-approved SDE 2
  corrections: one shared `SourceResult` contract for every source (no
  `list[Candidate]`-in-one-place-and-a-result-object-elsewhere split);
  explicit fallback semantics in `discover()` that preserve the original
  Apollo failure status/reason when substituting seed data; a fourth intake
  status (`GEMINI_ERROR`) so `INVALID_GEMINI_KEY` is reserved strictly for a
  rejected credential; a zero-Gemini country-extraction heuristic recognizing
  US/UK/Germany aliases; a final `audit` schema that includes `campaign_id`
  from the start, with `list_audit` querying it directly instead of a
  creation-time window; a corrected `POST /campaigns` sequence that creates
  the campaign (and its `campaign_id`) before any audit write; explicit
  hand-written status→action→banner maps (not `f"discovery.{status.value}"`);
  a 16px (`var(--space-4)`)-gapped two-banner stack using only existing
  info/warning tokens; a specified, deletable, DB-write-free verification
  script for invalid-credential paths instead of pasting fake keys through
  the UI; a computed-style-first, two-screenshot-max verification approach;
  "reuse"/"adapt" wording in place of "cherry-pick"; and a renamed,
  correctly-counted 17-file (not 13) review of every `slice-2-scratch`
  change. Also, per the instruction to read the finished file once for
  internal contradictions before committing, found and fixed six issues:
  two stale section cross-references left over from restructuring, one
  incomplete citation of collaboration.md's own rule 9, a real design gap
  where the described banner-rendering helpers took a live result object
  that `campaign_detail` (which only has persisted `action`/`detail`
  strings from `list_audit`) can't actually supply — resolved by adding an
  explicit action-string-keyed reverse lookup — and two type-annotation
  mismatches in the status-map code samples.
- Files or areas affected: `SLICE_2_PLAN.md` (new), `collaboration.md` (this
  entry). No application code, templates, styles, scripts, or dependency
  files were touched.
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of a full end-to-end read of the finished plan
  file specifically checking for internal contradictions (see corrections
  above) before staging the commit, and a `git status` check confirming
  only the two intended files were staged.
- Last known working state: `main` unchanged except for these two files;
  the application itself remains at the Slice 1 state — Slice 2 has not
  been implemented. A prior partial SDE 2 draft of `SLICE_2_PLAN.md` on
  `codex/sde-2-slice-2` was left untouched and unread, preserved via
  `git stash` on that branch (stash entry: "SDE2 partial SLICE_2_PLAN.md
  draft (preserved, not used, not read)").
- Known limitations: The plan's Apollo 401→`INVALID_KEY` mapping and
  Gemini's assumed 400/`INVALID_ARGUMENT`-with-"API key"-message or
  403→`INVALID_KEY` error shape are design assumptions, not yet confirmed
  against the live APIs (only Apollo's 403→insufficient-plan case has been
  confirmed live, in an earlier session). The plan requires the §14.1
  verification script to confirm or correct these before the mapping is
  relied on elsewhere in the implementation.
- Next action: Owner confirms this corrected plan has no further
  outstanding changes. Once confirmed, per collaboration.md rule 6, SDE 2
  (or SDE 1) may begin implementation — starting with the §14.1 isolated
  verification script to confirm the Apollo/Gemini error-shape assumptions
  live before wiring the rest of the route/audit/banner behavior around
  them.

## 2026-07-30 — Slice 2 implemented: B2B discovery via Apollo

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 2 (B2B discovery via Apollo) — full implementation
- Role: Implementer
- Implementation status: Complete
- Changes and corrections: Implemented `SLICE_2_PLAN.md` end to end,
  reviewing and adapting the `slice-2-scratch@96a01f8` files per §15's
  verdicts rather than cherry-picking them. New: `app/models.py` (Brief,
  Candidate, module-level `TargetType`), `app/llm.py` (Gemini transport,
  two-shot schema-aware retry, `LLMError`/`LLMErrorKind` distinguishing a
  rejected credential from every other failure), `app/agent/intake.py`
  (`IntakeResult`/`IntakeStatus` with the four-way status split and
  word-boundary country-alias extraction for the zero-Gemini heuristic
  path), `app/sources/base.py` (`SourceStatus`/`SourceResult`, the one
  contract every source's `search()` returns), `app/sources/apollo.py`
  (never raises; maps 200/401/403/network-error/other to the shared
  result, with a sanitizing `_safe_reason` helper), `app/sources/seed.py`
  (always returns `status=OK` from its own point of view; filters by
  `brief.target_countries`), `app/sources/__init__.py` (`discover()`,
  the only place that owns fallback semantics and preserves the original
  failure status/reason), `app/audit_banners.py` (explicit
  `DISCOVERY_MAP`/`INTAKE_MAP` plus a derived `BANNER_BY_ACTION` reverse
  index for rendering banners from persisted audit rows), and the three
  campaign templates. Modified: `app/db.py` (final `audit` schema with
  `campaign_id` from the start, the `llm`->`gemini` migration,
  `add_audit`/`list_audit`, `SETTING_KEYS` swap, plus the reused
  `campaign`/`target` tables and CRUD), `app/main.py` (the corrected
  7-step `create_campaign` sequence and a `campaign_detail` that derives
  banners from `list_audit` rather than a query string; `save_settings`'s
  `llm` param renamed to `gemini`), `app/templates/base.html` (Campaigns
  nav item), `app/templates/settings.html` (relabeled Gemini field),
  `app/static/css/app.css` (added `.page`/`.table*`/`.chips`/
  `.form-card--wide`/`.textarea`/`.target-type*` from v1 unchanged, plus
  new `.banners`/`.banner--info`/`.banner--warning`, token-only),
  `requirements.txt` (added `httpx`). One deliberate deviation from the
  plan: the Country column reads `raw_json`'s `country` field directly
  rather than the `location` string (which joins city/state/country) —
  needed to actually satisfy the plan's own stated column list
  (Company/Domain/Country/Size/Source) showing only the country. A
  temporary `scripts/verify_error_paths.py` (per §14.1) was written, run
  once against the real Apollo and Gemini APIs to confirm the error-shape
  mapping, and then deleted per the plan's default and collaboration.md
  rule 15 (not converted into a maintained test, since no test framework
  exists yet in this project).
- Files or areas affected: All files listed in SLICE_2_PLAN.md §16 (new
  and modified), plus this entry, PROGRESS.md, and DECISIONS.md.
- Verification: Ran the full §14.3 checklist against a second, temporary
  uvicorn instance on port 8001 (port 8000 was occupied by another
  session's server on this same machine; that server was left untouched).
  Confirmed: (1) the `llm`->`gemini` migration leaves zero `llm` rows on
  startup; (2) a fresh no-key workspace's business campaign returns 6 US
  seed rows with `intake.no_gemini_key` and `discovery.no_apollo_key`
  info banners, both audited; (3) the owner's real, plan-limited Apollo
  key (workspace "Demo Wellness Co") returns a live 403 that maps to
  `discovery.insufficient_plan` with a warning banner and seed fallback —
  the exact regression that motivated this corrected plan; (4) and (6)
  invalid-credential paths for Apollo (401) and Gemini, run once via the
  temporary script directly against both live APIs, confirming
  `INVALID_KEY`/`INVALID_GEMINI_KEY` map correctly before the script was
  deleted; (5) no-Gemini-key heuristic intake confirmed via the same
  no-key-workspace campaign; (7) a brief mentioning "UK and Germany" with
  no Gemini key extracts `["United Kingdom", "Germany"]` and the seed
  filter returns exactly the 4 non-US rows; (8) Workspace Alpha and Beta
  (from Slice 1) show zero campaigns and no audit/target rows leaked in,
  confirmed by direct `outpost.db` query; (9) computed-style checks
  confirmed `.banners` gap resolves to 16px (`--space-4`) and both
  `.banner--info`/`.banner--warning` colors resolve from
  `--info`/`--warning`(`-subtle`) in both light and dark themes (toggled
  live in the browser pane). Screenshots were not available in this
  session's headless browser tooling (the pane could not composite
  frames); computed-style verification — the plan's own preferred method
  — fully substituted for the two-screenshot allowance. No `outpost.db`
  rows were deleted or reset; verification created one new workspace
  ("No-Key Demo") and a few campaigns as normal product usage, left in
  place same as Slice 1's Alpha/Beta verification data.
- Known limitations: No automated test suite exists yet for this project,
  so the invalid-credential verification was one-time and manual (per
  plan §14.1's own instruction) rather than a repeatable regression test.
  The Apollo 401-vs-403 status mapping and Gemini's 400/403 credential-
  rejection mapping are both now confirmed live, but remain governed by
  each provider's own (undocumented-as-a-contract) conventions, as noted
  in SLICE_2_PLAN.md §4 and §3. Fit scoring, drafting, and the pipeline
  board are not part of this slice and arrive in Slices 3–4.
- Next action: Slice 3 (fit-scoring with citations), per SPEC.md §6 and
  PROGRESS.md. Model recommendation for that slice's planning is still
  owed to the owner before implementation begins, per CLAUDE.md.

## 2026-07-30 — Slice 3 plan created as SLICE_3_PLAN.md (planning only)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 3 (fit-scoring with citations) — planning only
- Role: Planner
- Implementation status: Not started
- Changes and corrections: Created `SLICE_3_PLAN.md` on `main`. Planning
  was done on the stronger reasoning model (Opus); the plan recommends
  Sonnet for execution and asks the owner to confirm the switch at the top
  of implementation. Two design forks were put to the owner and decided
  before the plan was written: (1) fit-scoring runs at discovery time
  (extending Slice 2's create_campaign sequence with a scoring step, so the
  detail page stays a pure read and each target is scored exactly once,
  honoring the memory non-negotiable); (2) one deliberately weak seed
  company is added to `seeds/companies.json` so the "weak target scores
  low" done-when is demonstrable on the zero-key demo path, not only with a
  live LLM — this changes the US seed count from 6 to 7. The plan reuses the
  Slice 2 patterns deliberately: the citation requirement is enforced by the
  Pydantic schema itself (FitReason requires a non-empty citation,
  FitAssessment requires >=1 reason, so no code path stores an uncited
  score); a deterministic heuristic scorer keeps the zero-key path scoring
  with honest, cited reasoning; ScoreStatus reuses the four-way
  rejected-credential-vs-other-failure split from intake; and a third
  explicit SCORING_MAP is added to audit_banners rather than interpolating
  enum values. The `target` table already has `fit_score`/`fit_reasons_json`
  from Slice 2's schema, so no migration is required. One simplification is
  flagged for owner awareness: scoring reads `candidate.raw` (identical to
  what `Source.evidence()` returns for both current sources today) rather
  than holding a live Source object, with a comment that Slice 5 wires
  `source.evidence()` if creator evidence diverges.
- Files or areas affected: `SLICE_3_PLAN.md` (new), `collaboration.md`
  (this entry). No application code, templates, styles, seeds, or
  dependency files were touched.
- Verification: Documentation-only change; no app code was written or run.
- Last known working state: `main` at the Slice 2 completion state; the
  application is unchanged. Only these two files differ.
- Known limitations: The heuristic scorer is a demo-mode stand-in, not a
  real fit model; it exists so the zero-key flow completes with cited
  reasoning. The at-discovery-time scoring's latency is bounded in practice
  (free Apollo -> <=10 seed rows; no-key -> instant heuristic), but a paid
  Apollo plan plus a live Gemini key would score up to 25 rows sequentially
  — a cost/latency cost that Slice 6's routing and early-exit address, out
  of scope here.
- Next action: Owner confirms this plan has no further outstanding changes.
  Once confirmed, per collaboration.md rule 6, implementation may begin on
  Sonnet — starting with the models.py schema and scoring.py, then the
  route/DB/audit/UI wiring, then the §11 verification.

## 2026-07-30 — Slice 2 hardening follow-up: redaction and UTF-8 safeguards

- Contributor/environment: SDE 2 / Codex desktop
- Slice: Slice 2 hardening
- Role: Implementer / Reviewer
- Implementation status: Incomplete
- Changes and corrections: Extended SDE 1's uncommitted hardening work only
  in the two owner-approved areas: Apollo and Gemini provider-message
  sanitizers now redact an echoed credential before audit/UI use;
  `SeedSource` now reads UTF-8 explicitly and converts decoding failures
  into `SEED_ERROR`. Added focused retained regressions for both providers
  echoing fake keys and malformed UTF-8 seed bytes.
- Files or areas affected: `app/sources/apollo.py`, `app/llm.py`,
  `app/sources/seed.py`, `tests/test_slice2_hardening.py`, and
  `collaboration.md`. All other hardening files remain SDE 1's existing
  uncommitted work.
- Verification: `python -m unittest tests.test_slice2_hardening -v` — 32
  tests passed in 0.799s. No real provider calls, keys, or `outpost.db`
  writes.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `7cf28bd`. Slice 2 hardening remains uncommitted. All retained tests pass.
- Known limitations: Live verification with a newly rotated Gemini key is
  still pending. `PROGRESS.md` and `DECISIONS.md` have not yet been updated.
  A non-blocking Starlette `TestClient`/httpx deprecation warning remains.
- Next action: SDE 1 resumes on this branch, verifies the diff, performs live
  verification only with a newly rotated key saved through Settings, updates
  `PROGRESS.md`, `DECISIONS.md`, and `collaboration.md` as needed, reruns
  tests, commits the complete hardening work, confirms a clean tree, and
  stops before Slice 3.

## 2026-07-30 — Slice 2 hardening completed: live verification, model fix, commit

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 2 hardening (branch `codex/sde-1-slice-2-hardening`)
- Role: Implementer / Reviewer
- Implementation status: Complete
- Changes and corrections: Resumed the branch left by SDE 2 (HEAD `7cf28bd`,
  8 corrections 1–7 already applied plus SDE 2's two owner-approved
  additions — echoed-credential redaction in `apollo._safe_reason`/
  `llm._safe_gemini_reason`, and UTF-8-safe seed reads). Reviewed SDE 2's
  diff and the extended 32-test suite; re-ran it clean before proceeding.
  Performed the owner's live-verification step (correction 8): started the
  app, asked the owner to paste a newly rotated Gemini key through the
  Settings page only (the key posted earlier in chat was treated as
  compromised and never used, read, or typed by this session), located the
  saved key by workspace/length/timestamp only (`SELECT ... length(key_value)
  ...`, never the value), and ran one real business campaign against it. The
  first live call surfaced a genuine finding the plan anticipated: Gemini
  rejected `gemini-2.5-flash` with "no longer available to new users."
  Per the hardening instructions' explicit stop condition, implementation
  paused and asked the owner before touching the model; current
  ai.google.dev/gemini-api/docs/models documentation was checked, the owner
  approved switching to `gemini-3.6-flash`, and live verification was
  re-run — confirming `intake.llm_ok`, a correctly LLM-parsed Brief
  (cleanly split product/audience/niche, not the heuristic's raw-text
  truncation), the key masked in Settings (`••••` + last 4 chars, same as
  Slice 1/2 behavior), and no key value anywhere in console output, audit
  `detail`, tracked files, `git diff`, or `git log --all -p`. Updated
  `PROGRESS.md` (hardening paragraph appended to the Slice 2 state) and
  `DECISIONS.md` (six new entries: the Apollo rate-limit/provider-error
  taxonomy, the seed-fallback-of-a-fallback behavior, SDE 2's credential
  redaction, `responseJsonSchema` provider-side enforcement, the
  `gemini-3.6-flash` model change with its live-verified justification, and
  the no-new-dependency `unittest` decision).
- Files or areas affected: `app/llm.py` (GEMINI_MODEL constant only, on top
  of SDE 1+2's existing hardening diff — no other code changes this
  session), `PROGRESS.md`, `DECISIONS.md`, `collaboration.md` (this entry).
  Full file list for the slice: `app/audit_banners.py`, `app/llm.py`,
  `app/main.py`, `app/sources/__init__.py`, `app/sources/apollo.py`,
  `app/sources/base.py`, `app/sources/seed.py`, `app/templates/
  settings.html`, `tests/__init__.py`, `tests/test_slice2_hardening.py`,
  plus the three docs files.
- Verification: `python -m unittest tests.test_slice2_hardening` — 32
  tests passed both before and after the model change. Live: one
  no-key/no-Apollo-key campaign (workspace "No-Key Demo", campaign id 6)
  correctly produced `intake.gemini_error` and a valid heuristic Brief
  against the still-configured `gemini-2.5-flash` (proving correction 1's
  graceful-degradation path fires on a real live error, not just a mocked
  one); one campaign after the model switch (same workspace, campaign id 7)
  produced `intake.llm_ok` with a genuinely LLM-parsed Brief. Settings page
  HTML confirmed to show only the masked placeholder for the saved key,
  never the raw value. `git status`/`git diff --stat` confirmed the working
  diff touches only the files listed above — no `outpost.db`, no
  `seeds/companies.json` changes. `git diff | grep -i AIza` and
  `git log --all -p | grep -i AIza` both came back clean.
- Known limitations: Apollo's 401-vs-403-vs-429 status convention and
  Gemini's credential-rejection error shape remain governed by each
  provider's own conventions rather than a documented contract, as already
  noted in SLICE_2_PLAN.md. The Starlette `TestClient`/httpx deprecation
  warning noted by SDE 2 is still present and non-blocking. Fit-scoring,
  drafting, and the pipeline board remain out of scope for this slice and
  arrive in Slices 3–4 as planned; Slice 3 was explicitly not started or
  implemented during this hardening pass.
- Next action: Owner reviews and merges/pushes this hardening branch as
  desired. Once merged, Slice 3 (fit-scoring with citations, already
  planned in `SLICE_3_PLAN.md`) is next — implementation still needs the
  owner's model-switch confirmation per CLAUDE.md before it begins.

## 2026-07-31 — Slice 3 plan corrected to v2.1 (planning only, no implementation)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 3 (fit-scoring with citations) — planning correction only
- Role: Planner / Reviewer
- Implementation status: Not started
- Changes and corrections: Rewrote `SLICE_3_PLAN.md` end to end in two owner
  review passes (v2, then v2.1) after the original plan was found to have
  seven gaps. Confirmed as a precondition that Slice 2 hardening was already
  committed and the tree clean (`b6aa26e` on this branch, 32 tests green), so
  correction 1 (finish hardening first) was already satisfied rather than
  needing new work. v2 corrections: (2) citations are now grounded, not just
  non-empty — the schema requires an `evidence_key`/`evidence_value` pair plus
  a non-empty `reason`, and `scoring.py` verifies that pair against the
  supplied evidence before any score is stored, discarding a fabricated
  citation to the per-target heuristic; (3) evidence is normalized at the
  `Source.evidence()` boundary (`normalize_evidence` in both `apollo.py` and
  `seed.py`, dispatched via a new `sources.evidence_for()`), so scoring never
  reads provider-specific keys like Apollo's `estimated_num_employees` vs
  seed's `employees`; (4) and (5) resolved together by an owner-confirmed
  design fork — scoring moved from a per-target loop to a single batch
  `FitBatch` LLM call, which bounds latency independent of target count, makes
  a credential failure a single 403 rather than a retry storm, and lets
  `add_scored_targets` persist every target and its score in one transaction
  (with an explicit zero-target branch that skips scoring and audits
  `scoring.skipped_no_targets`); (6) the verification section was rewritten
  around a retained `tests/test_slice3_scoring.py` instead of a disposable
  script, and the plan's file list now explicitly includes updating the
  Slice 2 6-US-seed-target assertion that the new weak seed company breaks;
  (7) the heuristic gained exact weights, tokenization, and missing-field
  rules plus a canonical test brief with an anchor-score table (weak seed
  scores 20, strongest seeds score 90), and the row-expand control became a
  real `<button>` with `aria-expanded` and native keyboard support instead of
  an optional mouse-only row-click. A second owner pass (v2.1) added four more
  corrections: `_is_grounded` now explicitly rejects a citation whose evidence
  value is `None` or blank (not just a missing key), closing a gap where
  `country: None` could have grounded a citation; `add_scored_targets` now
  guards `len(candidates) == len(scores)` before opening any connection,
  raising and writing zero rows on a mismatch rather than silently truncating
  via `zip`; the retained-test list was expanded with explicit missing/
  duplicate/out-of-range `target_index` cases (the plan's own §4.2 promised
  this behavior but the original test list only covered one ungrounded-
  citation case); and a live (not mocked) Gemini batch-scoring verification
  step was added, since mocks cannot prove Gemini's structured-output
  validator accepts the new nested `FitBatch` schema — the step reuses the
  Slice 2 hardening rule of a freshly rotated key pasted through Settings
  only, located by workspace/length/timestamp, never read or logged. Finally,
  a full read of the finished v2.1 file surfaced internal cross-reference
  drift left over from the two correction passes: three citations pointing at
  §8 (Audit + banner) for content that actually lives in §9 (UI/caret) or §11
  (Files changed, which is where the two verification subsections actually
  live); the two verification subsections were mis-numbered as standalone
  "9-note" headings instead of §11.1/§11.2; and the phrase "worst-status-wins"
  in the corrections table did not match the plan's actual (and correct)
  logic of explicit per-target aggregate counts feeding an honest status,
  rather than any single worst-status selection. All were corrected in place.
- Files or areas affected: `SLICE_3_PLAN.md` (rewritten to v2.1) and this
  `collaboration.md` entry. No application code, templates, styles, seeds, or
  dependency files were touched — this remains a planning-only change.
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of reading every file the plan's corrections
  reference against the actual committed Slice 2 code (`app/models.py`,
  `app/sources/base.py`, `app/sources/apollo.py`, `app/sources/seed.py`,
  `app/agent/intake.py`, `app/llm.py`, `app/db.py`, `app/main.py`,
  `app/audit_banners.py`, `app/sources/__init__.py`,
  `app/templates/campaign_detail.html`, `seeds/companies.json`, and
  `tests/test_slice2_hardening.py`) to ground every correction in what
  actually exists rather than assumption, followed by a full internal-
  consistency read of the finished v2.1 document (the pass that found the
  cross-reference and terminology drift corrected above) and a `grep` confirming
  no stray `§8`, `9-note`, or `worst-status-wins` references remained.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `b6aa26e` before this commit. `SLICE_3_PLAN.md` is the only file that
  changed content; the application itself remains at the Slice 2 (hardened)
  state — Slice 3 has not been implemented.
- Known limitations: The plan's live-Gemini-batch verification step (whether
  Gemini's structured-output validator accepts a `FitBatch` schema containing
  a nested list of objects, each with its own nested list of objects) remains
  unconfirmed until implementation actually runs it — this is flagged in the
  plan itself as a required step, not assumed to pass. The heuristic's anchor
  scores in §4.3 are computed by hand against the current `seeds/companies.json`
  and the one new weak entry; they have not yet been executed in code.
- Next action: Owner confirms v2.1 has no further outstanding changes (this
  commit represents that confirmed state per the owner's instruction to
  commit). Per collaboration.md rule 6, implementation may then begin on
  Sonnet (model switch already confirmed in this session) — starting with
  `app/models.py` (FitReason/FitAssessment/FitBatch), then the source
  normalization boundary, then `scoring.py`, then the route/DB/audit/UI
  wiring, then the retained tests in §11.1, then the live-Gemini-batch and
  computed-style verification in §11.2.

## 2026-07-31 — Slice 3 implemented: fit-scoring with grounded citations

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 3 (fit-scoring with citations) — full implementation
- Role: Implementer
- Implementation status: Complete
- Changes and corrections: Implemented `SLICE_3_PLAN.md` v2.1 in the order
  it specified. New: `app/agent/scoring.py` (`ScoreStatus`, `TargetScore`,
  `ScoreOutcome`, `score_batch()` — one structured `FitBatch` call scoring
  every discovered target at once; `_apply_batch()` resolving
  missing/duplicate/out-of-range `target_index` values and grounding every
  reason via `_is_grounded()` before trusting it; `_heuristic()`, the
  deterministic fallback with the exact weights the plan specified),
  `tests/test_slice3_scoring.py` (25 retained tests). Modified:
  `app/models.py` (`FitReason`/`FitAssessment`/`FitBatch`), `app/sources/
  apollo.py` and `app/sources/seed.py` (module-level `normalize_evidence()`
  mapping each provider's own fields to one shared shape; `evidence()` now
  delegates to it), `app/sources/__init__.py` (`evidence_for()` dispatcher
  keyed by `source_used`), `app/db.py` (`add_scored_targets` — one
  connection, one `executemany`, one commit, with the
  `len(candidates) == len(scores)` guard raising before any connection
  opens), `app/main.py` (`create_campaign`'s new zero-target branch and
  batch-scoring step; `campaign_detail`'s `_fit_class()` helper and
  `fit_reasons` parsing; the banner filter extended to `scoring.*`),
  `app/audit_banners.py` (`SCORING_MAP` + `BANNER_BY_ACTION` extension),
  `app/templates/campaign_detail.html` (Fit column; an accessible caret
  `<button>` with `aria-expanded`/`aria-controls`; a hidden `reasons-row`
  listing each grounded reason and citation), `app/templates/base.html`
  (added a `{% block scripts %}` — didn't exist before, needed for the
  caret's small vanilla-JS toggle), `app/static/css/app.css` (`.fit--high/
  mid/low`, `.caret` + rotation, `.reasons-row`/`.reason`/
  `.reason__citation`, `.visually-hidden`, tokens only), `seeds/
  companies.json` (added `Lakeside Software Studio`, the deliberately weak
  entry the plan specified), and `tests/test_slice2_hardening.py` (updated
  the now-invalid six-US-seed-target assertion to read the expected count
  from the seed file itself, plus new assertions that every target got a
  fit score and the weak company scores <70). One implementation-time
  discovery not anticipated by the plan text: the workspace-creation page's
  form wasn't reachable via this session's browser-automation click/type
  path (pre-existing Slice 1 code, untouched by this slice) — worked around
  by creating the one scratch verification workspace directly through
  `app.db.create_workspace()` (the same DB call the route itself makes) and
  driving the rest of the verification (workspace switching, campaign
  intake, results) through the browser normally, where those forms
  responded correctly to the same interaction methods.
- Files or areas affected: All files listed in SLICE_3_PLAN.md §11 (new and
  modified), `app/templates/base.html` (the one file added to that list
  during implementation, for the scripts block), plus this entry,
  `PROGRESS.md`, and `DECISIONS.md`.
- Verification: `python -m unittest discover -s tests` — 57 tests passed
  (25 new in `test_slice3_scoring.py`, 32 in the updated
  `test_slice2_hardening.py`), run repeatedly through the session and clean
  every time. Live, in a scratch workspace ("Slice 3 Verify", created with
  zero keys): (1) a zero-key business campaign correctly heuristic-scored
  all 7 US seed targets, with the weak seed lowest (20) and all seven
  landing in the `fit--low` band for that run's LLM-parsed-then-heuristic
  brief text (the plan's exact anchor numbers are pinned to the retained
  tests' fixed canonical brief, not arbitrary live text); the three-banner
  stack (`intake.no_gemini_key`/`discovery.no_apollo_key`/
  `scoring.no_gemini_key`) rendered correctly; direct `outpost.db` queries
  confirmed 7 scored targets with grounded `fit_reasons_json`, and that a
  different workspace saw none of them. (2) The owner pasted a freshly
  rotated Gemini key through Settings on that same workspace; this session
  never read the raw value, confirming only its presence via
  `length(key_value)` and `created_at`. A second campaign against that live
  key produced `scoring.llm_ok` — every one of 7 targets LLM-scored with
  every citation passing `_is_grounded()` against real seed evidence (zero
  heuristic fallbacks needed) — proving Gemini accepts the new nested
  `FitBatch` schema, which no mocked test could establish on its own.
  Confirmed no credential leakage: browser console was empty, `preview_logs`
  had no `AIza`-prefixed lines, `git diff | grep -i AIza` was clean, and
  `git log --all -p | grep -i AIza` only matched pre-existing documentation
  text from the Slice 2 collaboration entry (itself describing this same
  check), not a real key. (3) Computed-style checks confirmed `.fit--low`
  resolves to `--text-3` in both light and dark themes (toggled live via
  `data-theme`). (4) The caret's `aria-expanded`/`hidden` toggle and its 90°
  rotation transform were confirmed by invoking its real click handler
  (`button.click()`, which dispatches the same event the addEventListener
  listens for) after the browser tool's synthetic mouse click failed to
  register on this particular page in this session — isolated to be a
  browser-automation quirk on this run, not a code defect, since the
  identical click handler fired correctly once triggered. Native
  Enter/Space keyboard support follows from using a real `<button>` element
  and was not separately re-tested given that guarantee. No `outpost.db`
  rows were deleted or reset; verification added one new scratch workspace
  and two campaigns, left in place as normal product data, same as prior
  slices.
- Known limitations: The heuristic remains a demo-mode stand-in scored
  against whatever niche text intake produces for a given brief — its exact
  point values are anchored and tested against one canonical brief, not
  guaranteed to reproduce identical numbers for arbitrary live text (this is
  expected and by design, not a defect). No automated test exercises the
  live Gemini call itself (by definition, since it needs a real key) — that
  guarantee rests on this session's one-time manual verification, same
  category of limitation as Slice 2 hardening's live checks. Drafting, the
  approval queue, and the pipeline board remain out of scope for this slice
  and arrive in Slice 4.
- Next action: Owner reviews and merges/pushes this branch as desired. Once
  merged, Slice 4 (drafting, approval queue, pipeline) is next — model
  recommendation and plan review are still owed before that implementation
  begins, per CLAUDE.md.

## 2026-07-31 — Slice 3 hardening: four findings fixed before Slice 4

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 3 hardening (post-implementation findings, requested before
  starting Slice 4)
- Role: Implementer
- Implementation status: Complete
- Changes and corrections: Fixed four findings from the owner's route-level
  diagnostic of the just-shipped Slice 3 code, each verified against the
  actual code before changing anything: (1) `scoring.score_batch()` gained
  a `known_invalid_key_reason` keyword parameter; `create_campaign` now
  passes `intake_result.reason` through it whenever intake's status was
  `INVALID_GEMINI_KEY`, so a single campaign request with a rejected key
  makes exactly one live Gemini call (intake's) instead of two — scoring no
  longer re-asks a credential already known bad. (2)
  `apollo.normalize_evidence()`'s `name` field now defaults to "Unknown
  company" the same way `_to_candidate`'s `Candidate.name` already did (a
  malformed/empty Apollo organization object previously left
  `evidence["name"]` as `None` while the heuristic's zero-evidence fallback
  fabricated a `"this target"` citation that didn't match it — an
  ungrounded citation from the exact code meant to prevent them); the
  fallback branch itself was also changed to cite the real
  `evidence.get("name")` value or emit zero reasons, never a placeholder.
  (3) `_heuristic()`'s industry-overlap component now compares
  `_stemmed_tokens()` (a new minimal, longest-suffix-first word stripper —
  not a real stemmer) instead of exact tokens, so "distributors" and
  "distribution" count as the same term; the no-overlap explanation text
  was corrected from "doesn't match the brief's niche or product" to
  "doesn't match the brief's niche," since `brief.product` was never
  actually read by this component. (4) `app/sources/base.py` gained
  `coerce_int()`, used by both sources' `normalize_evidence()` to turn a
  numeric-looking string or float into an int (or `None`); `_heuristic()`
  also independently guards its own `employees` handling against a non-int
  or `bool` value before doing arithmetic, so the "never raises" contract
  holds even if some future caller's evidence isn't perfectly normalized.
- Files or areas affected: `app/agent/scoring.py` (the four fixes:
  `known_invalid_key_reason`, the fallback-citation fix, `_stem`/
  `_stemmed_tokens`, the employees type guard), `app/main.py`
  (`create_campaign`'s `known_invalid_reason` computation and pass-through),
  `app/sources/apollo.py` (`name` default, `coerce_int` on
  `estimated_num_employees`), `app/sources/seed.py` (`coerce_int` on
  `employees`), `app/sources/base.py` (new `coerce_int()`),
  `tests/test_slice3_scoring.py` (15 new tests: `KnownInvalidKeyTests`,
  `KnownInvalidKeyRouteTests`, `ApolloEmptyOrgGroundingTests`,
  `StemmingTests`, `EmployeesCoercionTests`), plus this entry, `PROGRESS.md`,
  and `DECISIONS.md`.
- Verification: `python -m unittest discover -s tests` — 72 tests passed
  (40 in `test_slice3_scoring.py` including the 15 new; 32 in
  `test_slice2_hardening.py`, unchanged and still green — the stemming
  fix's anchor-table regression guard confirmed all seven canonical-brief
  scores are unaffected by the change, computed by hand before writing the
  fix and matched by the retained test). One test
  (`KnownInvalidKeyRouteTests.test_one_campaign_request_makes_exactly_one_gemini_call`)
  runs a full `/campaigns` POST through `TestClient` with `app.llm.httpx.post`
  mocked to a 403 and asserts the mock's call count is exactly 1, directly
  proving finding 1 is closed at the route level, not just in an isolated
  unit test. Additionally ran three ad hoc (not retained) sanity scripts
  directly against the fixed functions to eyeball real output: the exact
  "US distributors for magnesium" phrasing from finding 3 now shows
  Northbridge Distribution Co. at 60 (was 40) and Cornerstone Wellness
  Distributors at 50 (was 30), with corrected reason text; an empty Apollo
  organization `{}` now normalizes to `name: "Unknown company"` and the
  heuristic's resulting single reason passes `_is_grounded()` (previously
  it would not have); `coerce_int` and the heuristic's defensive guard both
  confirmed via direct calls. No `outpost.db` writes, no real provider
  calls, no real keys.
- Known limitations: The stemmer is deliberately minimal (a fixed suffix
  list, longest-first, with a 3-character-minimum-root guard) and not a
  real linguistic stemmer — it closes the specific demonstrated gap
  (distribute/distributor/distribution/distributors) and was checked by
  hand for a few adjacent words (logistics, wholesale, services) to confirm
  no obviously wrong collisions, but it is not exhaustively verified
  against arbitrary English industry vocabulary. The heuristic's
  fully-degenerate zero-reasons path (finding 2's `test_fully_blank_evidence
  _yields_zero_reasons_not_a_fabricated_one`) cannot currently be produced
  by either live source (seed rows always have a name; Apollo's now always
  defaults to "Unknown company"), so it is a defensive guarantee for a case
  that shouldn't occur today, not a behavior exercised by any real path.
- Next action: Owner reviews and merges/pushes this branch as desired. Once
  merged, Slice 4 (drafting, approval queue, pipeline) is next — model
  recommendation and plan review are still owed before that implementation
  begins, per CLAUDE.md.

## 2026-07-31 — Slice 4 plan created as SLICE_4_PLAN.md (planning only)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 4 (drafting, approval queue, pipeline) — planning only
- Role: Planner
- Implementation status: Not started
- Changes and corrections: Created `SLICE_4_PLAN.md`. Planning was done on the
  stronger reasoning model (Opus 4.8, model switch confirmed by the owner
  before planning began); the plan recommends Sonnet for execution and asks
  the owner to confirm the switch at the top of implementation. Grounded the
  plan against the actual committed code first: confirmed no `draft` or `eval`
  table exists yet (Slice 4 adds only `draft`), that the `target.stage` and
  `audit.target_id`/`audit.draft_id` columns were already provisioned in Slice
  2's schema (so no migration to those tables is needed), and that the
  `--pl-*` pipeline-stage design tokens already exist in `tokens.css` for both
  themes (so the board needs no token additions). Per SPEC.md §6's instruction
  to apply the `beautiful-prose` and `humanizer` skills to the drafting
  prompt, both skills were loaded during planning and the drafting SYSTEM_PROMPT
  was authored in the plan itself (§4.2) rather than deferred to execution —
  the one genuinely writing-heavy part of the slice, kept on the strong model.
  The plan defines two separate state machines (draft status:
  pending/edited/approved/rejected; target stage:
  queued/contacted/replied/live/declined) with an explicit gate — approving a
  draft is what admits its target to the pipeline board — and reuses the
  Slice 2/3 patterns throughout: a status-carrying `DraftResult` mirroring
  intake/scoring, a deterministic zero-key heuristic that references the
  target's stored Slice-3 grounded citations (so demo mode completes and
  "references the cited evidence" holds by construction), the four-way
  credential-vs-error status split, structured output validated with retry,
  explicit audit action strings (no enum-string interpolation), and
  workspace-scoped DB functions. Six interpretive decisions are listed in §12
  for owner veto before implementation (chief among them: board membership =
  an approved draft; Approvals/Pipeline as workspace-level nav pages; buttons
  not drag; a light "name the company" personalization gate as the
  prose-suitable analog of Slice 3's exact-value grounding; `cost_tokens`
  created but left NULL until Slice 6; drafts generated on demand per selected
  target). A full read of the finished plan confirmed internal consistency
  (section cross-references, the files-changed list matching the body, and the
  non-negotiables mapping in §9).
- Files or areas affected: `SLICE_4_PLAN.md` (new) and this `collaboration.md`
  entry. No application code, templates, styles, seeds, or dependency files
  were touched — this is a planning-only change.
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of reading the actual committed Slice 2/3 code the
  plan builds on (`app/db.py` schema, `app/models.py`, `app/agent/scoring.py`,
  `app/main.py`, `app/audit_banners.py`, `app/templates/base.html` +
  `campaigns_list.html` + `campaign_detail.html`, `app/static/css/tokens.css`)
  to ground every "what already exists" claim, plus a `grep` confirming the
  `draft`/`eval` tables are absent and the `--pl-*` tokens are present.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `b48ee4a` before this commit. `SLICE_4_PLAN.md` is the only content that
  changed; the application itself remains at the Slice 3 (hardened) state —
  Slice 4 has not been implemented.
- Known limitations: The drafting prompt's real-world quality can only be
  judged against a live model — the plan flags a required live-Gemini
  verification step (§11.2) that a mocked test cannot substitute for. The
  personalization gate is deliberately lighter than Slice 3's grounding
  (prose can't be reliably value-checked); this is documented as a conscious
  trade-off, not an oversight.
- Next action: Owner confirms the plan has no further outstanding changes.
  Per collaboration.md rule 6, implementation may then begin on Sonnet
  (after the owner confirms the model switch, per CLAUDE.md) — starting with
  `app/models.py` (`OutreachDraft`) and `app/agent/drafting.py`, then the
  `draft` table + DB functions, then the routes/nav/UI, then the retained
  tests in §11.1, then the §11.2 no-key and live-Gemini verification.

## 2026-07-31 — Slice 3 second hardening pass: four more findings fixed before Slice 4

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 3 hardening, second pass (narrowly scoped correction pass
  requested explicitly before starting Slice 4; SLICE_4_PLAN.md and Slice 4
  implementation were not touched)
- Role: Implementer
- Implementation status: Complete
- Changes and corrections: Fixed four owner-specified corrections against
  the just-committed Slice 3 hardening code, each verified against the
  actual code before changing anything, and each confirmed live (not just
  via retained tests) before this commit. (1) Apollo's `_to_candidate` used
  `org.get("name", "Unknown company")` (default fires only on a missing
  key) while `normalize_evidence` used `raw.get("name") or "Unknown
  company"` (default fires on any falsy value) — two different expressions
  over the same value meant `{"name": ""}` could persist a blank
  `Candidate.name` while evidence read `"Unknown company"`. Added
  `app/sources/base.py`'s `canonical_name(raw_name, fallback)`, used
  identically at both call sites so the two can never diverge again. Seed
  data (ours, not external/untrusted) took the opposite fix: a blank or
  missing name in `seeds/companies.json` now raises inside
  `SeedSource._to_candidate` (caught by `search()`'s existing `except`,
  with `ValueError` added to that tuple) and routes through the existing
  `SEED_ERROR` path rather than ever becoming a `Candidate`. (2) The
  heuristic's fully-blank-evidence fallback returned `(0, [])` — a
  citation-free score, contradicting SPEC.md's "no score without a
  citation." `_heuristic()` now raises a new `UngroundedEvidenceError`
  instead when even the name field is unusable, and a new
  `scoring.assert_grounded(evidence_list, scores)` is called in
  `create_campaign` immediately before `db.add_scored_targets` as an
  independent, persistence-level second check (it doesn't trust that
  `_heuristic()` or the LLM-grounding path in `_apply_batch()` got it
  right). (3) The exact "US distributors for magnesium" demo phrase scored
  every seed company below the UI's 70-point threshold even after the
  first pass's stemming fix, because the niche text's incidental short
  words ("us") still inflated the industry-overlap denominator. Fixed with
  a general, length-based exclusion (`_significant_niche_tokens`: stemmed
  tokens shorter than 3 characters are dropped from the denominator) — not
  by hardcoding the phrase or any company name. A first attempt at this fix
  also tried excluding tokens shared with `brief.product`, and the retained
  test (which had hand-built a `Brief` with `product` deliberately
  different from `niche_or_industry`) passed — but live verification
  against the real app caught that this was wrong: `intake._heuristic_brief`
  (the actual zero-key code path) sets `brief.product` to the *identical*
  raw sentence as `niche_or_industry`, so that exclusion always emptied
  itself out via its own safety fallback and never once fired on real
  traffic. Removed the dead exclusion once understood, and rewrote the
  retained test to build its `Brief` via the real `intake._heuristic_brief`
  function instead of an idealized hand-built one, so it can't drift from
  reality the same way again. (4) `coerce_int()` raised on `NaN` and
  `+-infinity` (`int(float("nan"))`/`int(float("inf"))` both raise in plain
  Python) and silently truncated non-integral floats like `180.5` to `180`.
  Now checks `math.isfinite()` and integrality before converting; anything
  that fails either check becomes `None`, same as an unparseable string.
- Files or areas affected: `app/sources/base.py` (`canonical_name`,
  `coerce_int`'s NaN/inf/non-integral handling), `app/sources/apollo.py`
  (`canonical_name` at both call sites), `app/sources/seed.py` (blank-name
  rejection), `app/agent/scoring.py` (`UngroundedEvidenceError`,
  `assert_grounded`, the heuristic fallback raise, `_significant_niche_tokens`
  and its industry-block comment), `app/main.py` (`assert_grounded` wired
  into `create_campaign` before persistence, comment renumbering),
  `tests/test_slice3_scoring.py` (28 new tests across
  `CanonicalNameTests`, `ApolloNameConsistencyTests`, `SeedBlankNameTests`,
  `AssertGroundedTests`, `AssertGroundedRouteTests`,
  `NaturalNicheDilutionTests`, and additions to `EmployeesCoercionTests`;
  one existing test — the fully-blank-evidence case — updated to assert the
  new raise instead of the old `(0, [])`), plus this entry, `PROGRESS.md`,
  and `DECISIONS.md`. `SLICE_4_PLAN.md` was not opened or modified.
- Verification: `python -m unittest discover -s tests` — 100 tests passed
  (28 new, none removed; the one updated test now asserts
  `UngroundedEvidenceError` instead of `(0, [])`). Focused diagnostic
  scripts (not retained, run directly against the fixed functions): Apollo
  name consistency across `{}`, `{"name": None}`, `{"name": ""}`,
  `{"name": "   "}`, `{"name": "Acme Corp"}` — `Candidate.name` and
  `evidence["name"]` identical in every case; fully-blank evidence
  confirmed to raise `UngroundedEvidenceError` rather than score silently;
  `coerce_int` confirmed correct for `180`, `180.0`, `180.5`, `nan`, `inf`,
  `-inf`, `"180"`, `"nope"`, `True`, `None`. Live, in a scratch workspace
  ("Slice 3 Hardening 2 Verify", created with zero keys, no Apollo/Gemini
  key touched): a business campaign for "US distributors for magnesium"
  was created twice — the first attempt (before a full server restart)
  still showed pre-fix scores despite a logged `WatchFiles... Reloading`
  event, which turned out to be a stale-reload artifact, not a code defect;
  caught by checking the *persisted* `outpost.db` fit_score values directly
  rather than trusting the rendered page, and confirmed fixed after
  stopping the server, clearing `__pycache__`, and a clean restart. The
  corrected, final scores: Northbridge Distribution Co. 70, Cascade
  Logistics Partners 40, Meridian Health Supply 60, Ironclad Freight
  Solutions 40, Summit Supply Chain Group 40, Cornerstone Wellness
  Distributors 60, Lakeside Software Studio 20 — at least one clearly
  relevant distributor (Northbridge) at or above 70, Lakeside still well
  below, every expanded reason grounded (confirmed via the caret toggle),
  page loaded without error. Confirmed no real provider calls (Apollo/
  Gemini both absent from this workspace's settings), no credentials read
  or logged, `outpost.db` not reset or deleted (three new scratch
  workspaces/campaigns added as normal product data, same as every prior
  slice's verification), and `git diff --check` clean (only expected
  LF/CRLF line-ending notices, no real whitespace errors); `git diff` and
  the final file list contain no credential-shaped strings.
- Known limitations: The industry-overlap heuristic's length-based
  exclusion is still a blunt instrument — it happens to remove "us" because
  it's short, not because it recognizes country references specifically;
  a future niche phrase diluted by a *long* incidental word (a product name
  that isn't also short) would not be caught by this fix, same category of
  known limitation as the first hardening pass's stemmer being "minimal, not
  a real stemmer." The `UngroundedEvidenceError` raise path (both in
  `_heuristic()` and in `assert_grounded()`) remains unreachable by either
  current source given this pass's own fixes — a defensive guarantee for a
  case that shouldn't occur today, exercised only by direct unit tests, not
  by any live path.
- Next action: Owner reviews and merges/pushes this branch as desired. Once
  merged, Slice 4 (drafting, approval queue, pipeline) is next — model
  recommendation and plan review are still owed before that implementation
  begins, per CLAUDE.md. `SLICE_4_PLAN.md` (already committed) is untouched
  by this correction pass.

## 2026-07-31 — Slice 4 plan corrected to v2 (planning only, no implementation)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 4 (drafting, approval queue, pipeline) — planning correction only
- Role: Planner / Reviewer
- Implementation status: Not started
- Changes and corrections: Rewrote `SLICE_4_PLAN.md` end to end to v2,
  incorporating all seven owner-approved SDE 2 corrections consistently across
  architecture, routes, DB functions, UI, tests, verification, decisions, and
  the files-changed list. Confirmed the precondition first: Slice 3 hardening is
  committed and the tree clean (`fc5bc62` on `codex/sde-1-slice-2-hardening`,
  100 tests green), and grounded every correction against the actually-committed
  code (`app/db.py`, `app/main.py`, `app/agent/scoring.py`, `app/models.py`,
  `app/llm.py`, `app/sources/seed.py`/`apollo.py`/`base.py`,
  `app/audit_banners.py`, and the `campaign_detail.html`/`base.html` templates)
  rather than assumption. The seven corrections: (1) the two state machines are
  now enforced, not just enum-validated — explicit `DRAFT_TRANSITIONS` and
  `STAGE_TRANSITIONS` maps (module constants in `db.py`) shared by the DB guard,
  routes, and tests, with a documented controlled-response contract
  (cross-workspace/missing → not-found redirect; malformed enum → 422; illegal
  in-state transition → 409; double-submit race → `/approvals` redirect), and a
  same-stage request defined as an idempotent no-op that writes no misleading
  audit row. (2) Approve now commits the current textarea body — the approval
  submit carries `body`, and `approve_draft` captures it as `edited_body` if it
  differs, in the same atomic operation that approves; a retained route test
  types a change and approves without Save, then proves the Pipeline shows the
  changed text; the approval card is one form with three real submit buttons
  (save/approve/reject) posting to a single `/drafts/{id}/action` dispatcher.
  (3) LLM drafts are grounded in stored Slice 3 evidence — `OutreachDraft` gains
  `evidence_key`/`evidence_value`, and a runtime gate (`_is_draft_grounded`)
  verifies the pair matches one of the target's stored grounded fit reasons
  (transitively inheriting Slice 3's `_is_grounded` guarantee), the value is
  non-blank, the body references the value via a documented normalized-substring
  comparison, and the recipient identity is named when one meaningfully exists
  (target name, or handle/domain when the name is `base.DEFAULT_NAME`); the plan
  explicitly states `generate_structured`'s retry covers only JSON/schema
  validation, so semantic grounding is a separate layer that falls back
  deterministically to the heuristic (`HEURISTIC_FALLBACK`); the citation fields
  are validation-only metadata and add no `draft`-table column. (4) The
  heuristic is neutral and truthful — it states one stored evidence value with
  non-committal wording ("I noticed {name} works in {value}.") and never claims
  the fact proves fit, offers `brief.product` and one concrete ask, and a
  retained test with a deliberately poor-fit stored reason proves it never
  describes the target as an ideal partner or targeted market. (5)
  Campaign-detail links follow the lifecycle — Draft outreach / Draft again /
  Approvals-link / Pipeline-link — with a `_draft_cta` mapping table, rejected
  drafts visible only through Activity history, and no approved/rejected draft
  ever linked to a queue that excludes it. (6) Uniqueness and tenancy are
  enforced in the database — a partial unique index
  (`one_active_draft_per_target ... WHERE status != 'rejected'`) allows at most
  one non-rejected draft per `(workspace_id, target_id)`, `add_draft` uses an
  `INSERT ... SELECT` tenancy guard (zero rows → `NotFound`), every join
  qualifies both `workspace_id`s, and `list_pipeline_targets` de-duplicates via
  `GROUP BY target.id` with a deterministic approved-draft pick. (7) Each
  mutation and its audit row commit in one transaction via a shared internal
  `_insert_audit(conn, ...)` helper (the standalone `db.add_audit` is refactored
  to delegate to it and is retained only for the Slice 2/3 intake/discovery/
  scoring rows); on failure neither the state change nor the audit row remains,
  each audit row carries the correct workspace/campaign/target/draft ids, and
  the verification plan adds a test that a simulated failure leaves neither
  partial state nor a false audit. The §11 retained-test list was expanded to 15
  items covering all corrections plus a "nothing sends" test (patch `httpx.post`,
  assert the approve/stage/reject paths make zero outbound calls), and the
  manual/live steps were updated to verify the approved edited text appears on
  Pipeline and the audit trail matches each action exactly once. Assessed
  collaboration.md rule 7 (stop if a correction materially expands Slice 4
  beyond SPEC.md): none do — each tightens toward the non-negotiables (#4 audit,
  #5 structured output, #6 isolation) and SPEC §4/§6's "references the cited
  evidence"; the grounding change (correction 3) makes the slice more faithful
  to SPEC, not broader — so no scope-stop was needed. A full top-to-bottom read
  of the finished v2 confirmed all old contradictory wording was removed (the v1
  name-only personalization gate, and the v1 §12 decision 4 that called grounding
  "not" the approach), that all 20+ `§` cross-references resolve to real
  sections, and that the DB signatures, routes, UI behavior, audit table, test
  list, decisions, and files-changed list agree; one stray `§4.4-gate removed`
  reference misfiled under correction 2 was moved out.
- Files or areas affected: `SLICE_4_PLAN.md` (rewritten to v2) and this
  `collaboration.md` entry. No application code, tests, templates, CSS, schemas,
  `outpost.db`, or seed data were touched — planning only. `PROGRESS.md` and
  `DECISIONS.md` were intentionally not updated (no implementation yet).
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of reading every committed file the corrections
  reference (listed above) to ground each correction in real code, a full
  internal-consistency read of the finished v2 (the pass that found and fixed the
  misfiled cross-reference and confirmed the removed v1 gate/decision wording),
  a `grep` confirming every `§` reference maps to an existing header and no stale
  "name-only"/"personalization gate" wording remains except where the plan
  explicitly documents removing it, and `git diff --check` (clean; only the
  expected Windows LF→CRLF notice, no whitespace errors).
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `fc5bc62` before this commit. `SLICE_4_PLAN.md` is the only file whose content
  changed (plus this log entry); the application remains at the Slice 3
  (hardened) state — Slice 4 has not been implemented.
- Known limitations: The §4.4 body-grounding gate uses a normalized-substring
  comparison, which is deliberately lighter than Slice 3's exact citation match
  because prose is paraphrasable — a short numeric evidence value could
  substring-match incidentally (documented in §12 decision 4). The live-Gemini
  drafting-quality and live-grounding step (§11.2) can only be judged against a
  real key at implementation time; a mock cannot prove the prompt yields a human,
  grounded draft. Several interpretive decisions remain owner-vetoable in §12,
  notably: a single `draft.approved` audit row for approve-with-inline-edits
  (rather than a separate `draft.edited` + `draft.approved`), and the one-form/
  three-action approval endpoint shape.
- Next action: Owner confirms v2 has no further outstanding changes (this commit
  represents the corrected plan; §12 lists the interpretive decisions still open
  to veto). Per collaboration.md rule 6, implementation may then begin on Sonnet
  after the owner confirms the model switch (CLAUDE.md) — starting with
  `app/models.py` (`OutreachDraft`), then `app/agent/drafting.py`, then the
  `draft` table + partial unique index + atomic DB functions, then the routes/
  nav/UI, then the §11.1 retained tests, then the §11.2 no-key and live-Gemini
  verification.

## 2026-07-31 — Slice 4 plan corrected to v2.1 (planning only, no implementation)

- Contributor/environment: SDE 1 / Claude Code (session switched to Sonnet by
  the owner partway through this correction pass; see below)
- Slice: Slice 4 (drafting, approval queue, pipeline) — planning correction only
- Role: Planner / Reviewer
- Implementation status: Not started
- Changes and corrections: Revised `SLICE_4_PLAN.md` from v2 to v2.1,
  incorporating five owner-flagged blocking findings against v2, each
  grounded against the actually-committed Slice 2/3 code before being folded
  in (same discipline as the v2 pass). The owner switched this session's model
  to Sonnet via `/model` partway through the request; this remained a
  planning-only correction pass (grounded findings with concrete, specified
  fixes, not open-ended architectural judgment), so it continued rather than
  stopping to request an Opus switch — flagged in the plan's §0 model-status
  section for the owner's visibility. The five findings, added as items 8–12
  in a new §0.2: (8) an unapproved target could have its stage advanced by a
  direct POST, because `list_pipeline_targets` only *displayed* targets with
  an approved draft rather than the database *refusing* the mutation —
  `set_target_stage` now requires a workspace-scoped approved draft to exist
  before evaluating any stage transition, raising `NotFound` (deliberately
  indistinguishable from a missing/cross-workspace target, to avoid the
  response itself confirming a target's existence in another state) when none
  exists; a new public `has_approved_draft` supports direct testing of the
  same check `set_target_stage` performs internally. (9) The draft-creation
  route had no defined way to load the target and campaign brief — added
  `db.get_target(workspace_id, target_id)`, scoped identically to every other
  Slice 4 function, composed with the existing `db.get_campaign` to build the
  `Brief` the drafting module needs. (10) Human-submitted draft bodies were
  not server-validated, so a crafted POST could approve blank text — pulled
  `OutreachDraft.body_is_reasonable`'s 20–1500 character bound into one shared
  `validate_draft_body` function, called by both the Pydantic schema (model
  path) and `db.py`'s `save_draft_body`/`approve_draft` (human path); decided
  explicitly (owner's question) that yes, the same bound applies to human
  edits, since a blank approval would defeat "a human approves every send" as
  surely as a blank model draft would. (11) `draft.created`'s audit row
  couldn't explain the drafting outcome — `add_draft` now takes `DraftResult`'s
  `status` and `reason` and builds the audit `detail` from them
  (`status.value`, or `"{status.value}: {reason}"` when set); `DraftResult`'s
  docs were extended so `HEURISTIC_FALLBACK` now also sets a fixed,
  non-sensitive `reason` (the model's actual draft body is never echoed into
  an audit `detail`), closing the gap where "no key," "key rejected,"
  "provider error," and "grounding gate rejected the model" all collapsed to
  the same `model_used == "heuristic"` with no further explanation. (12) The
  route was going to catch every `sqlite3.IntegrityError` as a duplicate
  draft — added a dedicated `ActiveDraftExists` exception that `add_draft`
  raises only when the failure matches the `one_active_draft_per_target`
  index (identified by message-text matching, since SQLite does not raise a
  distinctly typed exception per constraint — flagged as a known limitation);
  every other `IntegrityError` now propagates unmapped as a genuine 500
  instead of being silently absorbed. Each finding was threaded through every
  affected section, not just its own paragraph: §3.1's transition tables and
  controlled-response contract, §4's `DraftResult` docs, §4.1's schema
  section, §5's function signatures and exception list, §6's route bodies and
  error handling, §8's audit table, §9's non-negotiables mapping, §10's
  files-changed list, five new items in §11.1's retained-test list (16–20,
  later trimmed to 16–19 after finding item 20 duplicated item 10's coverage
  during the final consistency read), and four new numbered decisions in
  §12/§13. A full top-to-bottom read of the finished v2.1 (required before
  committing, per the owner's instructions) found and fixed three residual
  inconsistencies: the duplicate test item just mentioned, a stale "this v2
  makes each mutation atomic" phrase in §0 that should have read "this plan"
  now that both v2 and v2.1 corrections stack on top of it, and §3's
  partial-unique-index description still saying a race "raises
  `sqlite3.IntegrityError`" without noting that §5's `add_draft` now
  translates that into `ActiveDraftExists` before it reaches a route.
- Files or areas affected: `SLICE_4_PLAN.md` (revised to v2.1) and this
  `collaboration.md` entry. No application code, tests, templates, CSS,
  schemas, `outpost.db`, or seed data were touched — planning only.
  `PROGRESS.md` and `DECISIONS.md` were intentionally not updated (no
  implementation yet).
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of grounding each finding against the specific plan
  lines the owner cited (confirmed each was real, not already addressed), a
  full internal-consistency read of the finished v2.1 (the pass that found
  and fixed the three residual inconsistencies above), a `grep` confirming
  every exception name (`NotFound`/`InvalidTransition`/`InvalidDraftBody`/
  `ActiveDraftExists`) and every `sqlite3.IntegrityError` mention is used
  consistently across sections, and `git diff --check` (clean; only the
  expected Windows LF→CRLF notice).
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `da74798` before this commit. `SLICE_4_PLAN.md` is the only file whose
  content changed (plus this log entry); the application remains at the
  Slice 3 (hardened) state — Slice 4 has not been implemented.
- Known limitations: `add_draft`'s `ActiveDraftExists` detection relies on
  matching SQLite's `IntegrityError` message text, since the driver does not
  expose a distinctly typed exception per constraint — documented in the plan
  itself (§12 decision 13) as slightly brittle to a SQLite message-format
  change across versions, with no better mechanism available short of a
  redundant pre-check that would reintroduce the exact race the index exists
  to close. The live-Gemini and no-key manual verification steps (§11.2)
  still require implementation to actually run; nothing about this pass
  changes what they need to prove.
- Next action: Owner confirms v2.1 has no further outstanding changes. Per
  collaboration.md rule 6, implementation may then begin on Sonnet (the model
  already active for this session) — starting with `app/models.py`
  (`OutreachDraft`), then `app/agent/drafting.py` (including
  `validate_draft_body`), then the `draft` table + partial unique index +
  atomic DB functions (including `get_target`, `has_approved_draft`, and the
  four typed exceptions), then the routes/nav/UI, then the §11.1 retained
  tests (19 items), then the §11.2 no-key and live-Gemini verification.

## 2026-07-31 — Slice 4 plan corrected to v2.2 (planning only, no implementation)

- Contributor/environment: SDE 1 / Claude Code (Sonnet)
- Slice: Slice 4 (drafting, approval queue, pipeline) — planning correction only
- Role: Planner / Reviewer
- Implementation status: Not started
- Changes and corrections: Revised `SLICE_4_PLAN.md` from v2.1 to v2.2,
  incorporating two more owner-flagged blocking findings, both real bugs a
  code-level read of the v2.1 plan surfaced. (13) A genuine circular import:
  v2.1 planned `validate_draft_body` inside `app/agent/drafting.py`, but
  `OutreachDraft` (in `app/models.py`) needs to call it from its own field
  validator — `models → drafting → models`. Confirmed the actual fix by
  reading the current import graph first (`app/models.py`: stdlib/pydantic
  only; `app/db.py`: already imports `Candidate` from `app.models` directly;
  `app/agent/scoring.py`: imports `app.models`, not `app.db`) before deciding
  where the function could live without creating any edge back into
  `app.agent.*`. Moved `validate_draft_body` to a module-level function in
  `app/models.py`; `OutreachDraft.body_is_reasonable` now calls it in the same
  module (no import at all), `db.py` imports it from `app.models` exactly
  where it already imports `Candidate`, and `drafting.py` needs no import of
  it whatsoever, since every `OutreachDraft` it constructs (LLM or heuristic)
  is validated by the schema at construction time. (14) A real concurrency
  gap: "same transaction" (v2's correction 7) made each mutation atomic with
  its own audit row, but did not stop two concurrent requests from both
  reading `status = 'pending'` before either wrote, both deciding the
  transition was legal, and both writing — e.g. two simultaneous approvals
  both succeeding and both writing a `draft.approved` audit row, violating
  the terminal-state and exactly-once requirements. Rather than adding
  `BEGIN IMMEDIATE` (the alternative the finding offered), chose a conditional
  `UPDATE ... WHERE status/stage IN (allowed source states)` plus a
  `cursor.rowcount` check for all four mutation functions
  (`save_draft_body`, `approve_draft`, `reject_draft`, `set_target_stage`) —
  reasoned through and documented explicitly in a new §5.1 why this is
  sufficient without `BEGIN IMMEDIATE`: with exactly one mutating statement
  per function, the `WHERE` clause itself is re-evaluated at the instant
  SQLite grants the write lock (not at an earlier Python-side read), so two
  concurrent connections' `UPDATE`s on the same row cannot both match — this
  relies on SQLite's ordinary writer serialization, which Python's `sqlite3`
  module already provides via its default (unmodified) `isolation_level` and
  connection `timeout`, so no change to `get_connection()` is needed.
  `approve_draft`'s "flags inline edits" logic was folded into the same
  statement via a `CASE` that compares the submitted body against the draft's
  own **immutable** `body` column (safe to reference with no race, since nothing
  ever writes to it after creation) rather than against a prior read of the
  mutable `edited_body` — a small, deliberate refinement of correction 2's
  semantics, called out explicitly as such. `set_target_stage` folds finding
  8's approved-draft gate into the same atomic statement via a correlated
  `EXISTS`, removing the last preliminary read from the success path
  entirely. Both findings were threaded through every affected section (§0.3,
  §3, §4.1, §5/§5.1, §6, §8, §9, §10, two new two-connection retained tests in
  §11.1 — items 20 and 21 — plus two new decisions in §12/§13). A full
  top-to-bottom read of the finished v2.2 (required before committing) found
  and fixed one real inconsistency introduced during drafting: item 21's
  illustrative concurrency example raced `queued → contacted` against
  `queued → replied`, but `replied` is already invalid from `queued` under
  the *static* transition map alone (`STAGE_TRANSITIONS["queued"] =
  {"contacted", "declined"}`) — that example didn't actually exercise the
  race, it just re-tested item 3's static-map check under a different name.
  Replaced it with a genuinely race-dependent pair: `"contacted"` and
  `"declined"`, both individually legal from `queued`, raced against each
  other — exactly one can win, and only a real concurrency race (not the
  static map) explains why the loser fails.
- Files or areas affected: `SLICE_4_PLAN.md` (revised to v2.2) and this
  `collaboration.md` entry. No application code, tests, templates, CSS,
  schemas, `outpost.db`, or seed data were touched — planning only.
  `PROGRESS.md` and `DECISIONS.md` were intentionally not updated (no
  implementation yet).
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of reading the actual current import graph
  (`app/models.py`, `app/db.py`, `app/agent/scoring.py`) to confirm finding
  13's cycle was real and to ground the fix in what already exists rather
  than assumption; reasoning through SQLite's and Python's `sqlite3` module's
  actual locking/isolation behavior (default deferred `isolation_level`,
  writer serialization, 5-second default connection `timeout`) to confirm the
  conditional-`UPDATE` design genuinely closes finding 14's race without
  `BEGIN IMMEDIATE`, rather than assuming it does; a full internal-consistency
  read of the finished v2.2 (the pass that found and fixed the item-21
  example above); a `grep` confirming every `validate_draft_body` mention
  correctly points to `app.models` (and the two remaining `app.agent.drafting`
  mentions correctly describe *avoiding* that import) and that all `§`
  cross-references resolve to real headers; and `git diff --check` (clean;
  only the expected Windows LF→CRLF notice).
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `9520aa3` before this commit. `SLICE_4_PLAN.md` is the only file whose
  content changed (plus this log entry); the application remains at the
  Slice 3 (hardened) state — Slice 4 has not been implemented.
- Known limitations: The conditional-`UPDATE`/`rowcount` concurrency design is
  explicitly scoped (§12 decision 14) to functions that mutate exactly one row
  with exactly one statement; a future function needing more than one mutating
  statement per transaction would need `BEGIN IMMEDIATE` or an equivalent
  revisited then. A request that cannot acquire SQLite's write lock within the
  default 5-second connection timeout raises `sqlite3.OperationalError:
  database is locked`, which is not specially handled — an accepted limitation
  of a single-file local SQLite app, not something this slice engineers
  around. The two new concurrency tests (§11.1 items 20–21) are real,
  multi-connection, multi-threaded tests against an on-disk temp SQLite file
  (not `:memory:`) and have not yet been run, since no code exists yet — like
  every other retained test in this plan, they remain a specification until
  implementation writes and runs them.
- Next action: Owner confirms v2.2 has no further outstanding changes. Per
  collaboration.md rule 6, implementation may then begin on Sonnet (the model
  already active for this session) — starting with `app/models.py`
  (`OutreachDraft` and `validate_draft_body`), then `app/agent/drafting.py`,
  then the `draft` table + partial unique index + the §5/§5.1 DB functions
  (including `get_target`, `has_approved_draft`, the four typed exceptions,
  and the conditional-`UPDATE` concurrency pattern), then the routes/nav/UI,
  then the §11.1 retained tests (21 items, including the two two-connection
  concurrency tests), then the §11.2 no-key and live-Gemini verification.
