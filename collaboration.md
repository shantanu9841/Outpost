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
