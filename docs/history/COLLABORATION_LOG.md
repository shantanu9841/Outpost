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

## 2026-07-31 — Slice 4 plan corrected to v2.3 (planning only, no implementation)

- Contributor/environment: SDE 2 / Codex desktop.
- Slice: Slice 4 — drafting, approvals, and pipeline; final planning correction only.
- Role: Reviewer / planner, editing with the owner's explicit authorization.
- Implementation status: Not started. No Slice 4 application code was written.
- Changes and corrections: Corrected the two remaining v2.2 concurrency defects. First, retained conditional `UPDATE ... WHERE ...` plus `cursor.rowcount` for `save_draft_body`, `approve_draft`, and `reject_draft`, where the source state is needed only as a guard. Changed `set_target_stage` to reserve SQLite's writer slot with `BEGIN IMMEDIATE`, then perform the workspace-scoped target read and approved-draft gate, same-stage no-op handling, transition validation, update, truthful `"old -> new"` audit insert, and commit under that one reservation. This preserves the authoritative old stage required by the audit and makes concurrent requests evaluate a serialized committed history. Second, corrected retained concurrency test 21: two identical `queued -> contacted` requests must yield exactly one success and one audit; a `contacted`/`declined` race may validly yield either one transition (`queued -> declined`, with the later contacted request rejected) or two ordered transitions (`queued -> contacted -> declined`), because `contacted -> declined` is legal. The test now accepts only those valid histories and verifies every audit detail against the actual predecessor stage. Revised all affected cross-references, implementation notes, non-negotiables, file responsibilities, test descriptions, and decisions; plan version is now v2.3.
- Files or areas affected: `SLICE_4_PLAN.md` and this `collaboration.md` entry only. No application code, tests, templates, CSS, schema, `outpost.db`, seed data, `PROGRESS.md`, or `DECISIONS.md` were changed.
- Verification: Full plan consistency review, targeted stale-wording searches, Markdown/diff checks, and `python -m unittest discover -s tests` (`Ran 100 tests`, `OK`). The future Slice 4 concurrency tests remain specifications until implementation.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD `39eb6c0d0d36eb7ee0fbb9238401813c1a08fc17` before this documentation-only commit. The application remains at the hardened Slice 3 state.
- Known limitations: `BEGIN IMMEDIATE` uses the existing default SQLite connection timeout. A request that cannot acquire the writer reservation within that timeout may raise `sqlite3.OperationalError: database is locked`; special lock-timeout handling remains intentionally out of scope for this local single-file app. No model/provider or live-Gemini verification is relevant to this planning-only correction.
- Next action: SDE 1 may implement Slice 4 from v2.3 after the required model checkpoint/reconfirmation, then execute the complete retained automated and manual verification plan before implementation sign-off.

## 2026-07-31 — Slice 4 implemented: drafting, approval queue, pipeline

- Contributor/environment: SDE 1 / Claude Code (Sonnet)
- Slice: Slice 4 (drafting, approval queue, pipeline) — full implementation
- Role: Implementer
- Implementation status: Complete
- Changes and corrections: Implemented `SLICE_4_PLAN.md` v2.3 end to end, in
  the order its own §0 "next action" specified. Confirmed the precondition
  first (branch `codex/sde-1-slice-2-hardening`, HEAD `11b71fc`, clean tree,
  100 tests green, Slice 4 not yet implemented) before reading every file the
  plan builds on (`app/db.py`, `app/models.py`, `app/main.py`,
  `app/agent/scoring.py`, `app/agent/intake.py`, `app/llm.py`,
  `app/sources/base.py`/`seed.py`/`__init__.py`, `app/audit_banners.py`, the
  existing templates, `app.css`, `tokens.css`) to ground every plan section
  against real committed code rather than assumption. New:
  `app/agent/drafting.py` (`DraftStatus`/`DraftResult`/`draft_outreach()` —
  the LLM path via `generate_structured(OutreachDraft, ...)`, a runtime
  `_is_draft_grounded()` gate checking the model's cited evidence pair
  against the target's stored Slice 3 `fit_reasons_json`, and the neutral,
  always-grounded `_heuristic_draft()` fallback), `app/templates/
  approvals.html` and `pipeline.html`, `tests/test_slice4_drafting.py` (70
  retained tests covering all 21 items in plan §11.1, including the two
  real two-connection concurrency tests against an on-disk temp SQLite
  file). Modified: `app/models.py` (`validate_draft_body` and
  `OutreachDraft`, placed here rather than in `drafting.py` per the plan's
  finding 13 to avoid a `models -> drafting -> models` import cycle);
  `app/db.py` (the `draft` table plus the `one_active_draft_per_target`
  partial unique index in `init()`; `DRAFT_TRANSITIONS`/`STAGE_TRANSITIONS`/
  `DRAFT_STATUSES`/`STAGES`/`STAGE_SET` module constants;
  `NotFound`/`InvalidTransition`/`InvalidDraftBody`/`ActiveDraftExists`; a
  shared `_insert_audit` helper with `add_audit` refactored to delegate to
  it; `get_target`, `add_draft`, `get_draft`, `get_active_draft_for_target`,
  `get_latest_draft_for_target`, `has_approved_draft`,
  `list_pending_drafts`, `save_draft_body`, `approve_draft`, `reject_draft`,
  `list_pipeline_targets`, `set_target_stage` — the three draft mutations
  use a conditional `UPDATE ... WHERE status IN (...)` plus `cursor.rowcount`
  per plan §5.1, and `set_target_stage` uses `BEGIN IMMEDIATE` before its
  scoped read per the plan's v2.3 correction); `app/main.py` (`nav_context`,
  the five new routes, `_draft_cta`, the campaign-detail Activity list, and
  every existing route's context dict switched to spread `nav_context`);
  `app/audit_banners.py` (the five Slice 4 action constants plus
  `ACTION_LABELS`/`label_for`); `app/templates/base.html` (Approvals +
  Pipeline nav items with the count pill) and `campaign_detail.html` (Draft
  column + Activity list); `app/static/css/app.css` (draft cards, the
  pipeline board and its five `--pl-*` stage pills, the nav count pill,
  activity list, `.btn--destructive` — token-only, no new colors or
  spacing). No changes to `tokens.css`, `seeds/`, or the `target`/`audit`
  table schemas (the plan's own §2 confirmed none were needed). One real
  bug was found and fixed during manual browser verification, not by any
  automated test: an HTML `<textarea>` submits `\r\n` line endings
  regardless of how its value was set, so an *unedited* approval's exact
  comparison against the stored (`\n`-only) body was always unequal, and
  every unedited approval was being misrecorded as "approved with inline
  edits." Fixed by normalizing CRLF/CR to LF inside the shared
  `validate_draft_body` (the one function both the schema and the human-body
  path already funnel through), with a regression test
  (`test_crlf_textarea_submission_without_edit_is_not_flagged_as_edited`)
  added to `tests/test_slice4_drafting.py` afterward. This is logged as its
  own DECISIONS.md entry rather than silently folded into the pre-existing
  "human body validator" entry, since it changed behavior after the initial
  implementation and tests were already green.
- Files or areas affected: All files listed above, plus this entry,
  `PROGRESS.md`, and `DECISIONS.md`.
- Verification: `python -m unittest discover -s tests` — 170 tests passed
  (70 new in `test_slice4_drafting.py`; 100 prior, all still green,
  confirming Slice 1-3 behavior is unchanged). Live, in a scratch workspace
  ("Slice 4 Verify", created directly via `db.create_workspace()` the same
  way prior sessions worked around this environment's workspace-creation-
  form browser-automation quirk, zero keys touched): a business campaign's
  7 seed targets were heuristic-scored as in Slice 3; drafted outreach for
  one target, edited the textarea, and clicked Approve **without** pressing
  Save — confirmed via direct `outpost.db` query that `edited_body` held the
  submitted (unsaved) text and the draft was `approved` in one step,
  matching correction 2; advanced that target Queued -> Contacted -> Replied
  -> Live through the Pipeline UI, confirming Live rendered with no further
  stage buttons (terminal); on a second, separately approved target, a
  crafted direct `fetch()` POST attempting the illegal `queued -> live` jump
  returned **409**, and a direct DB query confirmed both the target's stage
  and its audit trail were unchanged (no `target.stage_changed` row) —
  proving the transition map is enforced at the database boundary, not just
  hidden by the UI. Declined that same target legitimately from Queued via
  the UI. Drafted and then **rejected** a fourth target; confirmed its
  campaign-detail CTA correctly read "Draft again" (not "Draft outreach"),
  matching the rejected-vs-never-drafted distinction. Confirmed the full
  audit trail via direct `outpost.db` query matched the campaign-detail
  Activity list exactly, one row per action, no duplicates, no gaps.
  Confirmed via `fetch()` that a garbage `action` value on
  `/drafts/{id}/action` isn't needed as a separate check — already covered
  by the retained route-level 422 test. Computed-style checks (via
  `getComputedStyle`) confirmed all five `.pl-pill--*` classes resolve
  their `color`/`background-color` to the exact `--pl-*`/`--pl-*-subtle`
  token values in both light and dark theme (toggled live via the existing
  theme button), and confirmed the Approvals nav count pill resolves to
  solid `--accent`/`--accent-fg` only when the queue is non-empty, reverting
  to the neutral `--bg-subtle`/`--text-3` pill when empty. Screenshots were
  not available in this session's browser tooling (the pane could not
  composite frames, the same limitation noted in the Slice 3 collaboration
  entry) — computed-style and `get_page_text` verification fully
  substituted, per collaboration.md's own preference for text-based
  verification. `preview_logs` showed zero server errors across the entire
  manual verification session. `git diff --check` was clean (only the
  expected Windows LF->CRLF notices); a credential-string scan
  (`git diff | grep -iE "AIza|api[_-]?key"`) came back empty. No live-Gemini
  verification was performed — no Gemini key was available this session;
  this is recorded as an explicit, unverified gap below rather than implied
  to have passed. No `outpost.db` rows were deleted or reset; verification
  added one new scratch workspace and one campaign, left in place as normal
  product data, consistent with every prior slice's verification.
- Known limitations: The LLM drafting path (`DraftStatus.LLM_OK`, the
  `_is_draft_grounded` gate against a real model's output, and the drafting
  prompt's actual voice quality) is covered only by mocked tests this
  session — SLICE_4_PLAN.md §11.2's live-Gemini step could not be run
  because no Gemini key was available. This mirrors the same category of
  gap prior slices have flagged for their own live-only paths, and should
  be closed with a real key before treating the LLM drafting path as
  demo-proven. `add_draft`'s `ActiveDraftExists` detection still relies on
  matching SQLite's `IntegrityError` message text (inherited, unchanged,
  same limitation already documented in the plan). The CRLF normalization
  fix is scoped to `validate_draft_body`; any future code path that
  compares a stored body against raw form input without going through that
  function would reintroduce the same class of bug.
- Next action: Owner reviews and merges/pushes this branch as desired.
  Before relying on the LLM drafting path in a demo, run one live campaign
  against a freshly rotated Gemini key pasted through Settings (never read
  by the session performing it, located only by `length(key_value)` and
  `created_at`, per the Slice 2/3 hardening convention) and confirm
  `model_used == GEMINI_MODEL`, a human-reading draft, and the grounding
  gate passing on real model output. Once that's done (or the owner accepts
  the gap for now), Slice 5 (creator sources and demo mode) is next — model
  recommendation and plan review are still owed before that implementation
  begins, per CLAUDE.md.

## 2026-07-31 — Slice 4 approval reversion bug fixed after SDE 2 review

- Contributor/environment: SDE 2 / Codex desktop.
- Slice: Slice 4 post-implementation correction.
- Role: Reviewer / implementer, with the owner's explicit request to fix the
  verified defect.
- Implementation status: Complete.
- Changes and corrections: Fixed `approve_draft` losing the human's current
  textarea text when a prior Save had populated `edited_body` and the human
  later reverted the textarea to the immutable original `body` before
  approving. The atomic conditional UPDATE now sets `edited_body = NULL`
  when the normalized submitted body equals the original; otherwise it stores
  the submitted body. Consequently `COALESCE(edited_body, body)` always
  resolves to exactly what the human approved, and the approval audit's inline-
  edit detail remains consistent with the final effective text. Added the
  retained save -> revert -> approve regression covering the draft row,
  Pipeline text, and audit detail. Corrected the same stale `CASE` expression
  and explanation in `SLICE_4_PLAN.md`.
- Files or areas affected: `app/db.py`,
  `tests/test_slice4_drafting.py`, `SLICE_4_PLAN.md`, `PROGRESS.md`,
  and this `collaboration.md` entry. No schema, templates, CSS,
  `DECISIONS.md`, credentials, or local `outpost.db` data changed.
- Verification: Focused regression
  (`python -m unittest discover -s tests -p test_slice4_drafting.py -k reverting`)
  passed (`Ran 1 test`, `OK`). Full suite
  (`python -m unittest discover -s tests`) passed (`Ran 171 tests`, `OK`),
  increasing Slice 4's retained tests from 70 to 71 while preserving all 100
  pre-Slice-4 tests. `git diff --check` was clean before staging.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `0beba4d` before this correction; working tree contained only the five
  files listed above.
- Known limitations: The pre-existing live-Gemini verification gap is unchanged;
  no provider call or credential was needed for this deterministic DB fix.
- Next action: Owner may re-review this narrow correction. Slice 4 is ready for
  sign-off if the committed diff and 171-test result are accepted.

## 2026-07-31 — Live Gemini verification instructions added; Slice 4 gap closed

- Contributor/environment: SDE 2 / Codex desktop.
- Slice: Cross-session verification guidance and Slice 4 live-provider closure.
- Role: Reviewer / documentation maintainer, with the owner's explicit request.
- Implementation status: Documentation complete; no application code changed.
- Changes and corrections: Added a durable `CLAUDE.md` rule explaining that
  provider credentials are workspace-scoped rather than global, naming
  `Slice 3 Verify` (workspace id `5`) as the currently approved Gemini
  verification workspace, and requiring metadata-only discovery
  (`length(key_value)`/`created_at`) with no raw-secret inspection, output,
  logging, copying, or Git storage. Future full UI verification in another
  workspace must have the owner paste the key through that workspace's
  Settings page. Updated `PROGRESS.md` to close its stale live-Gemini gap.
- Files or areas affected: `CLAUDE.md`, `PROGRESS.md`, and this
  `collaboration.md` entry only. No code, tests, schema, credentials, or
  local database rows changed.
- Verification: Before this documentation change, a DB-write-free live
  `draft_outreach` call used `db.get_settings(5)` without printing the
  settings and returned `DraftStatus.LLM_OK`,
  `model_used == "gemini-3.6-flash"`, no fallback, and no error reason.
  The generated body and credential were not printed. Documentation diff and
  credential-pattern checks were clean; the previously verified 171-test code
  state is unchanged.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, HEAD
  `1db9676` before this documentation-only commit.
- Known limitations: The approved workspace id/name is local state and may
  change; the instruction explicitly requires metadata-only revalidation and
  owner confirmation if it is absent. Free-tier quota can still produce a
  future 429 even though today's live call succeeded.
- Next action: SDE 1 should follow `CLAUDE.md`'s live-provider procedure
  whenever a slice needs real Gemini verification; no Slice 4 provider gap
  remains as of this check.

## 2026-07-31 — Documentation context optimized before Slice 5

- Contributor/environment: SDE 2 / Codex desktop.
- Slice: Cross-project documentation architecture, completed before Slice 5
  planning with the owner's explicit approval.
- Role: Implementer / documentation maintainer.
- Implementation status: Complete; no executable behavior changed.
- Changes and corrections: Reorganized documentation around progressive
  disclosure rather than forcing every SDE session to ingest all history.
  Preserved the pre-refactor `collaboration.md` and `DECISIONS.md`
  byte-for-byte first as `docs/history/COLLABORATION_LOG.md`
  (canonical Git-blob SHA-256 for `ba94834:collaboration.md`
  `398646895EEAFEDDD7B0D9C4DC421B69ACD23F1F288A8D37BAE8A616B592DAA8`)
  and `docs/history/DECISIONS_LOG.md` (baseline SHA-256
  `976928A2B8A5B3B85923C662D4814DE8C7850A3C6EA0987CE0112277B80B16D2`).
  Moved the completed Slice 2–4 plans with Git to
  `docs/plans/completed/`. Rewrote `CLAUDE.md` as the compact permanent
  rulebook plus task-based context routing and precedence; rewrote
  `PROGRESS.md` as a current Slice 0–4 snapshot and exact Slice 5
  prerequisites; rewrote `DECISIONS.md` as an active-constraint index;
  and rewrote `collaboration.md` as active rules/current handoff/recent
  activity with detailed future entries routed to this history file. Updated
  source and retained-test docstrings/comments that named the moved completed
  plan paths; no executable statement or assertion changed.
- Files or areas affected: `CLAUDE.md`, `PROGRESS.md`,
  `DECISIONS.md`, `collaboration.md`,
  `docs/history/COLLABORATION_LOG.md`,
  `docs/history/DECISIONS_LOG.md`, the three completed plan paths under
  `docs/plans/completed/`, and plan-reference documentation in
  `app/db.py`, `app/main.py`, `tests/test_slice3_scoring.py`,
  and `tests/test_slice4_drafting.py`. No schema, runtime logic, template,
  CSS, seed, dependency, credential, or `outpost.db` data changed.
- Verification: Pre-refactor baseline was clean at `ba94834` with 171 tests
  passing. After the refactor, `python -m unittest discover -s tests` again
  passed all 171 tests. The mandatory active reading pack measures
  approximately 8,878 tokens by characters/4 (10,559 including
  `design.md`), down from roughly 46,000, an approximately 81% reduction.
  Cold-start checks confirmed that the next slice, test baseline, tenant and
  credential rules, demo mode, human approval, nothing-sends boundary, atomic
  audit, SourceResult contract, Gemini workspace procedure, both Slice 5
  research prerequisites, single-implementer rule, and archive routing are
  all discoverable without history. Every active Markdown path resolves;
  non-archived plan references point to the moved paths; `git diff --check`
  was clean; and no Gemini-key-shaped value appeared in the active diff.
- Last known working state: Branch
  `codex/sde-1-slice-2-hardening`, baseline HEAD `ba94834` before
  this documentation-only refactor. Application behavior remains the
  verified Slice 4 state.
- Known limitations: Token counts are estimates (characters/4), not provider-
  tokenizer measurements. Compact active summaries now require disciplined
  maintenance; if an active constraint changes, both its summary and detailed
  history must change together. Archives remain intentionally large and must
  be loaded when the routing triggers in `CLAUDE.md` apply.
- Next action: Owner reviews the compact context, preserved archives, and
  measured savings. After approval, begin Slice 5 planning with its model
  checkpoint and provider research; do not implement Slice 5 from historical
  plans.

## 2026-07-31 — Canonical collaboration archive hash corrected

- Contributor/environment: SDE 2 / Codex desktop.
- Slice: Documentation maintenance before Slice 5 planning.
- Role: Implementer / documentation maintainer.
- Implementation status: Complete; documentation-only correction.
- Changes and corrections: Replaced the pre-refactor `collaboration.md`
  baseline hash with the SHA-256 of the canonical LF-normalized Git blob at
  `ba94834:collaboration.md`. The previous value was calculated from a Windows
  CRLF working-tree copy. Archived content was already preserved correctly and
  was not changed by this correction.
- Files or areas affected: `docs/history/COLLABORATION_LOG.md` and the compact
  handoff in `collaboration.md`. No code, tests, schema, credentials, plans, or
  local database rows changed.
- Verification: Confirmed the corrected value against the Git blob, checked
  the focused diff, and ran `git diff --check`. The retained 171-test baseline
  remains unchanged because no executable file changed.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`, baseline
  HEAD `d7a4f11` before this documentation-only correction.
- Known limitations: SHA-256 values must be compared against canonical Git
  blobs rather than line-ending-converted Windows working-tree files.
- Next action: SDE 1 may begin Slice 5 planning after the owner gives the model
  checkpoint and planning instruction. Slice 5 implementation remains blocked
  until the owner approves its plan.

## 2026-07-31 — Slice 5 plan created (planning only)

- Contributor/environment: SDE 1 / Claude Code.
- Slice: Slice 5 (creator sources and demo mode) — planning only.
- Role: Planner.
- Implementation status: Not started.
- Changes and corrections: Created docs/plans/SLICE_5_PLAN.md from the
  owner-approved Slice 5 decisions. Planning was on Opus; the plan recommends
  Sonnet for execution and asks the owner to confirm the switch at the top of
  implementation. Provider research was verified against official sources on
  2026-07-31: chosen creator actors are apify/instagram-scraper ($2.70 per
  1,000 results on the Free plan) and clockworks/tiktok-scraper (advertised
  from $1.70 per 1,000 results; Free-tier $3.70 per 1,000 per its tiered
  table, plus a $0.001 actor-start fee), both called via Apify's REST
  run-sync endpoint with the workspace's own token (BYO-key). The YouTube
  quota claim was corrected to the current official model: search.list has a
  dedicated bucket of 100 calls/day at 1 unit each, separate from the
  10,000-units/day pool used by channels.list enrichment; live YouTube
  requires a workspace key (no keyless discovery — a correction to SPEC §5
  and the Settings hint). Owner-approved decisions captured verbatim in §1:
  deterministic priority routing (Apify -> YouTube -> creator seed, no
  auto-aggregation); Apify runs both IG and TikTok actors and merges
  normalized candidates with explicit full-success / partial-success (new
  SourceStatus.PARTIAL_RESULTS with sanitized provenance) / dual-failure
  behavior and a deterministic failure precedence
  (INVALID_KEY > INSUFFICIENT_PLAN > RATE_LIMITED > PROVIDER_ERROR >
  NETWORK_ERROR); a target-type-aware additive creator heuristic (followers
  25, niche/bio overlap 60, country 15) that leaves the business path and its
  Slice 3 anchor scores unchanged; a five-category creator seed spread
  (strong, partial, geographic-mismatch, weak/low-follower, irrelevant); and
  the evidence_for(source_used, target_type, candidate) contract change so
  business and creator seed evidence cannot collide. Live provider
  HTTP-status -> typed-status mappings are explicitly marked as assumptions
  until a §7.2 deletable script confirms them, as Slice 2 did for
  Apollo/Gemini. The plan lists explicit acceptance criteria and retained
  tests for Apify full success, partial success, dual failure, status
  precedence, YouTube routing, seed fallback, creator scoring,
  business-score regression protection, tenant isolation, sanitized audit
  details, and the zero-key demo.
- Files or areas affected: docs/plans/SLICE_5_PLAN.md (new), collaboration.md
  (current handoff and recent activity), and this history entry. No
  application code, tests, seeds, templates, styles, schema, or dependency
  files were touched.
- Verification: Documentation-only change; no app code was written or run.
  Verification consisted of confirming the target branch
  (codex/sde-1-slice-2-hardening) was clean at d54c0d8 with no other-SDE
  activity in the reflog before writing; re-verifying the YouTube quota model
  and both Apify actor prices against their official pages/docs; and a staging
  check (git status / git diff --check / a credential-shaped-value scan)
  confirming only the three intended documentation files changed with no
  credential-shaped values and no executable files.
- Last known working state: Branch codex/sde-1-slice-2-hardening at d54c0d8
  before this planning commit; the application remains at the verified Slice 4
  state. Only the three documentation files differ.
- Known limitations: The Apify and YouTube HTTP-status mappings, the actor
  output field names, and the pricing/quota figures are current best
  information (provider-controlled, dated 2026-07-31) and must be re-verified
  live before being relied upon in implementation. A live creator end-to-end
  depends on the owner providing a free YouTube and/or Apify key; absent that,
  verification will be seed plus mocked.
- Next action: Owner and SDE 2 review docs/plans/SLICE_5_PLAN.md. After
  approval and the model-switch checkpoint, implementation may begin on
  Sonnet, starting with the §7.2 live error-shape verification before wiring
  the sources, route, scoring, audit, and UI. Do not implement until then.

## 2026-07-31 — Slice 5 plan corrected after owner review (planning only)

- Contributor/environment: SDE 1 / Claude Code.
- Slice: Slice 5 (creator sources and demo mode) — planning only.
- Role: Planner.
- Implementation status: Not started.
- Changes and corrections: Applied the six owner-required corrections to
  docs/plans/SLICE_5_PLAN.md. (1) Made the LLM scoring path target-type-aware,
  not only the heuristic: SYSTEM_PROMPT and _build_prompt in
  app/agent/scoring.py currently say 'candidate company' and omit target_type,
  so a creator campaign scored by Gemini would get a business prompt; the plan
  now selects business vs creator prompt wording by brief.target_type and
  carries target_type into the prompt, preserving business wording and leaving
  the prompt-independent heuristic (and its anchor scores) unchanged. (2)
  Replaced token-in-URL transport with header authentication — Apify
  'Authorization: Bearer' and YouTube 'X-goog-api-key' — so no request URL is
  credential-bearing, per official Apify guidance. (3) Replaced the
  run-sync-get-dataset-items endpoint with start-run + bounded polling and
  explicit caps: per-request httpx timeout (30s), actor-run timeout (120s),
  poll budget (150s), maxItems (search limit), and maxTotalChargeUsd (0.10),
  all verified against docs.apify.com/api/v2 and the act-runs POST reference;
  run-lifecycle terminal states added to the §5.4 status mapping. (4)
  Corrected the false 'never duplicated into SQLite' statement: BYO-keys are
  stored once in workspace-scoped workspace_setting.key_value (masked) and
  never copied into scripts, logs, audit details, URLs, screenshots, or
  tracked files. (5) Specified the exact creator follower bands
  (10k-500k -> 25; 1k-9,999 or 500,001-2M -> 15; <1k or >2M -> 5; missing ->
  0), their inclusive boundary behavior with a per-boundary test list, and the
  practical 85-point ceiling when country is absent (common on IG/TikTok). (6)
  Renamed the creator seed-load failure action to discovery.creator_seed_error
  to avoid colliding with business discovery.seed_error in the globally keyed
  BANNER_BY_ACTION/ACTION_LABELS maps, and added a non-collision test.
- Files or areas affected: docs/plans/SLICE_5_PLAN.md (revised), collaboration.md
  (handoff and recent activity), and this history entry. No application code,
  tests, seeds, templates, styles, schema, or dependency files were touched.
- Verification: Documentation-only change. Re-verified the Apify Bearer-header
  recommendation and the timeout/maxItems/maxTotalChargeUsd run parameters
  against official Apify API docs before citing them. Confirmed the target
  branch clean, staged only the intended documentation files, ran
  git diff --check, and scanned the staged diff for credential-shaped values
  (none) and non-.md files (none).
- Last known working state: Branch codex/sde-1-slice-2-hardening; the previous
  planning commit (963a90b) plus this corrections commit change only
  documentation. The application remains at the verified Slice 4 state.
- Known limitations: Apify/YouTube HTTP-status and run-lifecycle mappings, the
  actor output field names and defaultDatasetId shape, the follower bands (a
  demo heuristic, not a calibrated model), and the pricing/quota figures remain
  best-current information to be re-verified live before being relied upon. A
  live creator end-to-end still depends on the owner providing a free YouTube
  and/or Apify key.
- Next action: Owner and SDE 2 review the corrected docs/plans/SLICE_5_PLAN.md.
  After approval and the model-switch checkpoint, implementation may begin on
  Sonnet, starting with the §7.2 live error-shape verification. Do not
  implement until then.
## 2026-07-31 — Slice 5 implementation-readiness corrections by SDE 2 (planning only)

- Contributor/environment: SDE 2 / Codex.
- Slice: Slice 5 (creator sources and demo mode) — planning only.
- Role: Implementation reviewer and plan corrector, after explicit owner
  approval of the proposed corrections.
- Implementation status: Not started.
- Changes and corrections: Closed the remaining SDE 2 review findings. Replaced
  the deprecated Apify `/v2/acts/` route with canonical `/v2/actors/`.
  Restricted live verification to a synthetic invalid-key case and
  owner-authorized bounded happy paths; explicitly prohibited intentionally
  exhausting quota, provoking rate limits, manufacturing billing/plan
  failures, consuming remaining credit, or forcing paid actor failures.
  Required official documentation plus mocked retained tests for unsafe-to-
  induce mappings and allowed naturally observed sanitized cases to be
  recorded separately. Added retained-test requirements that pin header-only
  authentication, absence of credential query parameters, per-run timeout/item/
  charge caps, per-request timeouts, wall-clock polling, every run lifecycle
  state, and start/poll/fetch failures. Defined controlled
  `raw["_outpost_platform"]` provenance so Instagram/TikTok/YouTube/seed
  identity survives the existing batch-level source write and reaches evidence
  and the creator table without a schema migration. Updated `PROGRESS.md` so
  active context truthfully says the corrected plan exists and implementation
  remains unapproved and unstarted.
- Files or areas affected: `docs/plans/SLICE_5_PLAN.md`, `PROGRESS.md`,
  `collaboration.md`, and this history entry. No application code, retained
  tests, seeds, templates, styles, schema, dependencies, or local database rows
  were changed.
- Verification: Full diff reviewed; `git diff --check` clean; stale/unsafe
  wording scan found no matches; aggregate credential-pattern scan found zero
  credential-shaped values; only Markdown documentation files changed; retained
  Slice 0–4 suite passed 171/171 via `python -m unittest discover -s tests`.
- Last known working state: Branch `codex/sde-1-slice-2-hardening` based on
  planning commit `66e607b`; application behavior remains the verified Slice 4
  state with 171 retained tests passing.
- Known limitations: Slice 5 provider HTTP/run-lifecycle mappings remain
  explicit assumptions where they cannot be safely live-observed. Current
  provider pricing and output shapes are provider-controlled and must be
  rechecked during implementation without unsafe failure induction. A live
  happy path still requires an owner-provided workspace key.
- Next action: Owner reviews the fully corrected Slice 5 plan. Only after
  explicit implementation approval and the model-switch checkpoint may Slice 5
  implementation begin on Sonnet, starting with the safe checks permitted by
  §7.2. Do not implement until then.

## 2026-07-31 — Slice 5 implemented: creator sources and demo mode

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 5 (creator sources and demo mode) — full implementation
- Role: Implementer
- Implementation status: Complete
- Changes and corrections: Implemented `docs/plans/completed/SLICE_5_PLAN.md`
  end to end on Sonnet, with no material deviation from the owner-approved
  plan. New: `app/sources/youtube.py` (search.list + one batched
  channels.list, `X-goog-api-key` header auth, strict per-request timeout,
  never raises); `app/sources/apify.py` (`ApifySource` running the Instagram
  and TikTok actors via start-run -> bounded-poll -> fetch, `Authorization:
  Bearer` header auth, named `RUN_TIMEOUT_SECS`/`MAX_ITEMS`/
  `MAX_TOTAL_CHARGE_USD`/`REQUEST_TIMEOUT_SECS`/`POLL_INTERVAL_SECS`/
  `POLL_BUDGET_SECS` constants, an injectable sleep/monotonic clock so tests
  can drive the poll loop without a real wait, merge-with-precedence per
  §5.3); `seeds/creators.json` (five-row strong/partial/geographic-
  mismatch/weak/irrelevant spread, engineered against a "wellness fitness
  mindfulness" brief to score 100/80/65/40/5 — confirmed live); and
  `tests/test_slice5_creators.py` (35 new retained tests, one per §7.1
  acceptance criterion group). Modified: `app/sources/base.py`
  (`SourceStatus.PARTIAL_RESULTS`); `app/sources/seed.py`
  (`SeedSource("creator")` reads `creators.json` with no country
  pre-filter — unlike business — so the geographic-mismatch row
  reaches scoring instead of being discovery-filtered away; new
  `normalize_creator_evidence`, `_to_creator_candidate`); `app/sources/
  __init__.py` (`_discover_creator`'s Apify-then-YouTube-then-seed priority
  routing, `_fallback_to_creator_seed`, and `evidence_for(source_used,
  target_type, candidate)` now dispatching seed's business/creator
  normalizers by `target_type`); `app/agent/scoring.py`
  (`SYSTEM_PROMPT_BUSINESS`/`SYSTEM_PROMPT_CREATOR` selected by
  `_system_prompt(target_type)`, `_build_prompt` now carries `target_type`
  and labels rows "creator"/"company", `_heuristic` dispatches to the
  renamed `_heuristic_business` — byte-identical logic — or the new
  `_heuristic_creator` with the exact §6.3.3 follower bands);
  `app/audit_banners.py` (`CREATOR_DISCOVERY_MAP`,
  `CREATOR_DISCOVERY_OK_ACTIONS`, and a `discovery_action_for(source_attempted,
  status)` dispatcher — one addition beyond the plan's literal §6.4
  text: a creator `OK` needs the source-specific silent action
  (`discovery.apify_ok` vs `discovery.youtube_ok`), which a map keyed only by
  `SourceStatus` cannot express, so dispatch is by `source_attempted` first
  and then, only for `OK`, by which source actually succeeded); `app/main.py`
  (wires the new dispatcher into `create_campaign`, adds `_platform_label`
  and `target["platform"]` to `campaign_detail`, and updates the
  `evidence_for` call site for the new `target_type` parameter); three
  templates (`campaign_new.html` enables the creator radio;
  `campaign_detail.html` renders a target-type-aware table — Creator/
  Handle/Platform/Followers vs Company/Domain/Country/Size; `settings.html`
  corrects the YouTube hint to state a workspace key is required for live
  discovery, no keyless language). One incidental fix to a pre-existing
  Slice 3 test's implicit assumption: `discovery_action_for` treats any
  `source_attempted` other than `"apify"`/`"youtube"` as business (not only
  `"apollo"` specifically), which keeps
  `test_slice3_scoring.AssertGroundedRouteTests` (a mock using the
  synthetic, non-production `source_attempted="seed"`) passing without
  modifying that retained test file.
- Files or areas affected: All files listed in SLICE_5_PLAN.md §8 (new
  and modified), plus this entry, `PROGRESS.md`, `DECISIONS.md`, and
  `collaboration.md`. `docs/plans/SLICE_5_PLAN.md` moved to
  `docs/plans/completed/SLICE_5_PLAN.md` per the established convention (no
  content change). No `requirements.txt` change and no schema migration, as
  the plan specified.
- Verification: §7.2's safe live check ran first, via a temporary
  DB-write-free script (`scripts/verify_slice5_error_shapes.py`, deleted
  immediately after per collaboration.md rule 11) hitting the real Apify and
  YouTube APIs with synthetic, obviously-fake credentials only: Apify
  start-run with a bogus Bearer token returned `401`/
  `user-or-token-not-found`; YouTube `search.list` with a bogus
  `X-goog-api-key` header returned `400`/`INVALID_ARGUMENT`/"API key not
  valid. Please pass a valid API key." — both confirming the plan's
  `INVALID_KEY` mapping and the header-only auth transport (no
  credential-bearing URL) before any application code was written. No owner
  `youtube`/`apify` key was available or authorized this session, so §7.2's
  owner-authorized bounded happy-path leg was not run. Ran the full retained
  suite after every implementation step: 206/206 tests pass
  (`python -m unittest discover -s tests`) — 171 pre-existing tests
  unchanged plus 35 new tests covering every §7.1 acceptance criterion
  (Apify full/partial/dual-failure and status precedence; YouTube-vs-Apify
  routing priority; zero-key seed fallback with the `discovery.no_creator_key`
  banner; the creator seed spread's ranking discrimination with every
  reason grounded; all eight follower-boundary pairs plus missing/
  non-integer-followers and the country-absent 85-point ceiling; the
  target-type-aware LLM prompt/system-text; a re-pinned business anchor
  score, Cornerstone Wellness Distributors -> 90, reached through the same
  public `_heuristic()` dispatcher creator scoring now shares; the business/
  creator discovery action-key non-collision; tenant isolation of creator
  targets/audit rows; sanitized-reason redaction of an injected fake key;
  Apify/YouTube transport assertions — Bearer/`X-goog-api-key` headers,
  no credential query params, `timeout`/`maxItems`/`maxTotalChargeUsd` on
  every actor start, per-request timeouts, a mocked poll clock proving the
  wall-clock budget is honored, and every start/poll/fetch failure plus
  every terminal run state mapping without raising; and platform provenance
  surviving persistence into `campaign_detail`'s rendered table). Also ran a
  live browser session against the real app and the real `outpost.db` (a new
  workspace, "Slice 5 Verify", id 8, created and left in place as normal
  product usage, matching prior slices' verification precedent): confirmed
  the creator radio is enabled on `/campaigns/new`; submitted a zero-key
  creator campaign and confirmed the resulting `/campaigns/{id}` page shows
  the target-type-aware Creator/Handle/Platform/Followers columns, all three
  platform labels (YouTube, Instagram, TikTok) rendering correctly for the
  five creator-seed rows, the `discovery.no_creator_key` info banner text,
  and differentiated (non-uniform) fit scores; confirmed `/settings` shows
  the corrected YouTube hint; confirmed the full draft -> approve -> pipeline
  stage-change flow completes for a creator target through the real routes
  (matching the mocked integration test). Confirmed via `getComputedStyle`
  in both themes that no new CSS token was needed — every new element
  reuses existing classes (`.table`, `.badge`, `.banner--info`) — and
  that dark (`bg` `#09090B`, `text` `#FAFAFA`, `bg-subtle` `#131316`) and
  light (`bg` `#FAFAFA`, `text` `#18181B`, `bg-subtle` `#F4F4F5`,
  `.banner--info` background `#DBEAFE`) all resolve to design.md's exact
  token values. Screenshots were unavailable in this session's headless
  browser pane (same limitation noted in the Slice 2 entry); computed-style
  verification substituted, per collaboration.md rule 10's stated
  preference. No `outpost.db` rows were deleted or reset; the only local
  state change was the new "Slice 5 Verify" workspace and its one campaign,
  created as normal product usage.
- Known limitations: No live Apify or YouTube creator discovery run has been
  performed — both require an owner-provided workspace key, and none was
  authorized this session. Every §5.4 HTTP-status mapping beyond the
  confirmed `INVALID_KEY` case (insufficient-plan, rate-limit,
  provider-error, and every Apify run-lifecycle terminal state) remains an
  explicit assumption grounded in official documentation and mocked tests
  only, per the plan's own §9 — SLICE_5_PLAN.md explicitly forbids
  deliberately reproducing quota/rate-limit/billing/plan failures to close
  this gap live. Apify/TikTok's exact output field names (`fans` vs
  `followers`, `nickname` vs `nickName`) are taken from the actor's
  documented schema and tolerated defensively (a missing field becomes
  `None`, never a crash) but are unconfirmed against a real dataset item.
  The creator follower bands are a demo-mode heuristic choice, not a
  calibrated model, as the plan itself states.
- Next action: Commit this work (application code, seeds, tests, and
  documentation together). Then Slice 6 (evaluation and cost-aware
  routing) per SPEC.md §6 — model recommendation and a plan-mode
  confirmation against SPEC.md are still owed to the owner before that
  slice's implementation begins.

## 2026-07-31 — Slice 5 implementation review corrections

- Contributor/environment: Codex desktop, SDE 2 implementation reviewer and
  correction implementer, working in
  `C:\Users\shant\claude_code_projects\Outpost`.
- Slice: Slice 5 — creator sources and demo mode, post-implementation
  hardening on top of `b2ddd11`.
- Role: Review findings confirmed independently, then corrected after the
  owner's explicit "fix all" instruction.
- Implementation status: Complete.
- Changes and corrections: Updated the TikTok converter to parse the current
  Apify actor's published nested `authorMeta` creator fields (`id`, `name`,
  `nickName`, `signature`, `fans`, `region`) while retaining defensive flat
  aliases and rejecting rows with no creator metadata. Creator adapters now
  use creator-specific identity fallbacks. Changed YouTube search parsing so
  invalid JSON, non-object bodies, missing/non-list `items`, malformed rows,
  and missing/blank channel ids map to a typed `PROVIDER_ERROR`; only a valid
  empty `items` list remains an `OK` empty search. Tightened Apify polling so
  the deadline is checked after sleep and after the response, and each poll
  request timeout is capped to the remaining wall-clock budget.
- Files or areas affected: `app/sources/apify.py`,
  `app/sources/youtube.py`, `tests/test_slice5_creators.py`, `PROGRESS.md`,
  `collaboration.md`, and this history entry. No schema, dependency, seed,
  template, or owner database change.
- Verification: Added six retained tests: documented nested TikTok mapping,
  malformed TikTok metadata rejection, malformed YouTube 200 classification,
  final partial-sleep budget exhaustion, remaining-budget request-timeout
  capping, and response-after-deadline rejection. Targeted source suite passes
  19/19. Full suite passes 212/212 via
  `python -m unittest discover -s tests` (171 pre-Slice-5 tests plus 41 Slice-5
  tests). `git diff --check` passes; credential-pattern scan and final clean
  worktree check are required before commit.
- Last known working state: All Slice 5 zero-key, provider-fallback, scoring,
  tenant-isolation, audit, provenance, and lifecycle tests pass with the
  corrected adapters and strict poll deadline.
- Known limitations: No owner-authorized live Apify/YouTube happy-path run was
  performed. TikTok normalization is grounded in the current official schema
  and retained fixtures but remains unconfirmed against a live owner dataset.
- Next action: Commit this correction set, then return to owner review. Slice 6
  remains gated on its required model recommendation and plan confirmation.

## 2026-08-01 — Slice 6 plan created (planning only)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 6 (evaluation and cost-aware routing) — planning only
- Role: Planner
- Implementation status: Not started (plan under owner review)
- Changes and corrections: Created `docs/plans/SLICE_6_PLAN.md` on top of the
  post-fix Slice 5 baseline (`b640b49`, 212 tests). Planning was done on
  Opus 4.8; the plan recommends Sonnet for execution and asks the owner to
  confirm the switch at the top of implementation. Four design forks were put
  to the owner and decided before the plan was written: (1) the escalation
  tier is a stronger paid Gemini model under strict BYO-key billing —
  escalation may fire only when the workspace has its own `gemini` key AND has
  explicitly opted into the paid tier AND the target is high-fit; with no key
  or no opt-in the app stays fully functional on the zero-cost heuristic/free
  path and never escalates silently, and any provider charges belong to the
  workspace owner's own Google project; (2) eval is LLM-as-judge with a
  deterministic heuristic fallback (the same four-status pattern as
  intake/scoring/drafting); (3) cost is shown as exact token counts plus a
  labelled estimated dollar figure from a documented, adjustable, provider-
  controlled rate table; (4) the exact stronger model id and its pricing are
  deferred until current official availability is verified — no paid live
  verification without explicit owner authorization, mocked retained tests
  otherwise — so escalation is fully built and mocked-tested but physically
  cannot fire until the owner sets a verified `ESCALATION_MODEL` constant and
  opts a workspace in. The plan reuses the established slice patterns: the
  LLM judge returns a Pydantic-validated `EvalResult` with one retry via
  `llm.py`; `llm.generate_structured` keeps its exact current signature (a new
  `generate_structured_measured` returns token usage + model, so no Slice 2–5
  test or caller changes); a new idempotent `eval` table (SPEC §3) and the
  already-reserved `draft.cost_tokens` are written atomically with the draft
  and its audit rows; the paid-tier opt-in is stored as a non-masked
  `paid_tier` `workspace_setting` (recommended, no migration) with a dedicated
  Settings checkbox; and `routing.py` owns the high-fit gate
  (`HIGH_FIT_THRESHOLD = 85`, reusing design.md's success band), the
  confidence early-exit (`CONFIDENCE_THRESHOLD = 80`), the escalation
  orchestration, and per-outreach cost summation across every LLM call made.
  Four open decisions are flagged for owner review in the plan's §8 (opt-in
  storage mechanism; the two threshold defaults; the 4×0–25 eval scale; and
  whether the escalation-case dollar estimate using the final model's rate is
  acceptable vs. a stored exact-cost column). Fifteen acceptance criteria,
  each with at least one mocked retained test, cover cost recording, per-draft
  eval, the LLM-judge/heuristic split, both no-silent-escalation guards
  (no key; no opt-in), the high-fit gate, the confidence early-exit, the
  escalation-unavailable path, cross-call cost summation, atomic creation,
  the running cost-per-outreach figure, tenant isolation, Slice 2–5 backward
  compatibility, estimated-$ rendering, and sanitized audit/cost details.
- Files or areas affected: `docs/plans/SLICE_6_PLAN.md` (new), `collaboration.md`
  (handoff + recent activity), and this history entry. No application code,
  tests, templates, styles, seeds, schema, or dependency files were touched.
- Verification: Documentation-only change; no app code was written or run. The
  212-test Slice 5 baseline is unchanged. Verified the working tree was clean
  at `b640b49` before and that only the three intended documentation files are
  staged.
- Last known working state: `codex/sde-1-slice-2-hardening` at `b640b49`; the
  application is unchanged at the Slice 5 completion state. Only these
  documentation files differ.
- Known limitations: The stronger model id and pricing are unverified by
  design (owner-gated, decision 4); every cost/eval/escalation mapping in the
  plan is to be covered by mocked retained tests during implementation, with
  any live check requiring explicit owner authorization for a single bounded
  free-tier call only. The plan's open §8 decisions are not yet resolved.
- Next action: Owner completes review and resolves the §8 open decisions.
  After explicit implementation approval and the model-switch confirmation,
  implementation may begin on Sonnet, starting with the `models.py`/`llm.py`/
  `eval.py`/`routing.py` core, then the DB/route/UI wiring, then the §6
  verification. Do not implement until then.

## 2026-08-01 — Slice 6 plan corrected to v2 (planning only)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 6 (evaluation and cost-aware routing) — planning only, v2
- Role: Planner / correction implementer
- Implementation status: Not started (plan under owner review)
- Changes and corrections: Applied all ten owner-approved SDE 2 review
  findings against v1 (`2f991a5`) to `docs/plans/SLICE_6_PLAN.md`. (1)
  `app/llm.py`'s `_resolve_key` is corrected to drop the `GEMINI_API_KEY`
  environment fallback entirely, making every LLM workflow strictly
  workspace-key-only — a change to already-shipped Slice 2 code, not only
  new Slice 6 modules, since intake/scoring/drafting share the same
  `_resolve_key`. (2) The single-token `LLMResult` is replaced by a
  `TokenUsage` dataclass carrying model id plus independently nullable
  prompt/input, candidates/output, thinking, and total token counts. (3)
  `generate_structured_with_usage` and `LLMError` both accumulate a
  `list[TokenUsage]` across every attempt actually made — the first try, the
  retry, and any attempt whose overall call ultimately falls back to a
  heuristic — so spent tokens are never dropped just because the structured
  parse failed; `TokenUsage` is defined to hold only a model name and plain
  integers/`None`, so attaching it to `LLMError` cannot leak a payload or
  credential. (4) "No model call was made" (a known `0`) and "a call
  happened but usageMetadata was missing or malformed" (unknown, `None`) are
  now distinct at every layer, including the aggregate `draft.cost_tokens`
  and `estimated_cost_microusd`, which become `NULL` (never a fabricated
  `0`) whenever any contributing attempt's total is unknown; one
  documented exception is specified — `thoughtsTokenCount` absent from an
  otherwise-present `usageMetadata` block is treated as a genuine, known
  zero (a normal case for non-thinking model calls), distinct from the
  whole-block-missing case. (5) Dollar accounting is corrected to price
  each attempt at that attempt's own model's per-input/output/thinking
  rate — never one blended total-token rate, and never mixed-model usage
  priced only at the final/escalated model's rate — computed once at
  creation time and persisted as a new `cost_breakdown_json` (per-attempt
  detail) plus integer `estimated_cost_microusd` (millionths of a dollar,
  to avoid floating-point drift), so a later change to the pricing constant
  table can never retroactively alter a historical draft's stored estimate.
  (6) A rejected key discovered during default drafting
  (`DraftStatus.INVALID_GEMINI_KEY`) is now terminal for the whole routing
  request: eval is called with the already-known rejection reason (skipping
  its own live call) and escalation eligibility is forced false regardless
  of fit/opt-in, with a call-count acceptance test added. (7) The `eval`
  table's schema is corrected to `draft_id INTEGER NOT NULL UNIQUE
  REFERENCES draft(id)`, enforcing exactly one eval per draft at the SQLite
  level (not just in application logic), while keeping explicit
  `workspace_id` scoping and the atomic draft/eval/cost/audit creation
  transaction. (8) The deterministic heuristic rubric, previously described
  only in prose, is now fully specified: personalization and specificity
  are binary (25 or 0) grounded checks reusing `drafting._recipient_identity`
  and `drafting._parse_fit_reasons`/`_norm_for_substring` rather than
  duplicating that logic; non-genericness is two independent sub-checks (a
  0-or-15 banned-phrase check against a new shared `BANNED_FILLER_PHRASES`
  constant moved out of `drafting.SYSTEM_PROMPT`'s prose and into real
  Python, and a 0-or-10 sentence-length-variety check) summing to one of
  four exact totals; clear-ask counts question-mark-terminated sentences
  (1 -> 25, 0 -> 0, 2+ -> 10); a missing-body defensive path is specified;
  and the exact nested `EvalDimension` (points + justification, each
  independently validated) / `EvalRubric` / `EvalResult` (with a
  model-validator enforcing `score` equals the sum of the four dimensions'
  points) Pydantic shapes are given in full. (9) All "free model"/"free
  tier" language is replaced with "default model" and "estimated paid
  list-price cost" throughout the plan and the UI copy it specifies,
  including a corrected Settings hint for the existing Gemini key card
  (whose current copy references the environment fallback removed by
  correction 1); the plan states plainly that default drafting and the LLM
  judge both spend the workspace owner's real Google-project quota once a
  key is present, and that the only genuinely zero-cost state is no
  workspace key at all. (10) The plan adds an explicit completion-gating
  decision: Slice 6's code, tests, and UI may be complete and committed
  while `ESCALATION_MODEL` stays unset, but Slice 6 itself is not marked
  complete against `SPEC.md` §6 until the owner approves a specific
  stronger model id and it passes the same kind of safe verification gate
  Slice 5 used for Apify/YouTube — never a paid live call without explicit
  authorization. Also resolved, per the owner's explicit instruction rather
  than left open as in v1: paid-tier opt-in storage is now a firm decision
  (a dedicated, idempotently migrated `workspace.paid_tier_enabled INTEGER
  NOT NULL DEFAULT 0` column, guarded by a `PRAGMA table_info`-based
  add-column-if-missing helper reused for `draft`'s two new cost columns) —
  product configuration, not a credential, workspace-scoped, and default
  off so every existing Slice 1-5 workspace is unaffected. The proposed
  `HIGH_FIT_THRESHOLD = 85` and `CONFIDENCE_THRESHOLD = 80` (both stated as
  inclusive) and the four-dimension x 0-25 eval scale are kept as v1
  proposed them, per the owner's explicit instruction. `app/agent/
  drafting.py` is added to Slice 6's in-scope/files-touched lists (it was
  absent from v1) since it now hosts `BANNED_FILLER_PHRASES`, gains a
  `usage: list[TokenUsage]` field on `DraftResult`, and gains an optional
  `model` parameter on `draft_outreach` so routing's escalation call reuses
  the same function rather than duplicating drafting logic. The acceptance
  criteria list (plan section 6) grew from 15 to 22 items, adding explicit
  coverage for retry/failure usage accumulation, mixed-model pricing,
  unknown-vs-zero usage, environment-key exclusion (both for drafting/
  routing and for eval/escalation), terminal invalid-key call-count,
  inclusive threshold boundaries at both edges, opt-in default-off/
  isolation, eval uniqueness at the database level, atomic rollback, and
  UI wording (no "free" language). Left explicitly open in the plan's own
  section 8, not resolved by this pass: the stronger model id and its
  pricing (owner-gated per correction 10); `gemini-3.6-flash`'s exact
  current per-token-type rates, deliberately left as unfabricated
  placeholders in the plan text, to be filled from the official pricing
  page before implementation rather than guessed now; the plan's own
  interpretation of thinking-token absence as a known zero, flagged for the
  owner to confirm against current official documentation if desired; and
  the exact LLM-judge prompt wording, left to implementation.
- Files or areas affected: `docs/plans/SLICE_6_PLAN.md` (rewritten, v1 ->
  v2), `collaboration.md` (handoff + recent activity), and this history
  entry. No application code, tests, templates, styles, seeds, schema, or
  dependency files were touched.
- Verification: Documentation-only change; no app code was written or run.
  The 212-test Slice 5 baseline is unchanged and was re-confirmed passing
  before this revision began. `git diff --check` passes on the three
  changed files. A credential-shaped-string scan (API-key/token/Bearer
  patterns) across the three changed files found no matches. Confirmed via
  `git status` that only `docs/plans/SLICE_6_PLAN.md`, `collaboration.md`,
  and `docs/history/COLLABORATION_LOG.md` are staged, and that the working
  tree is clean immediately after the commit.
- Last known working state: `codex/sde-1-slice-2-hardening` at `b640b49`;
  the application is unchanged at the Slice 5 completion state. Only these
  three documentation files differ from that baseline.
- Known limitations: Every numeric pricing constant in the plan is an
  explicit, labelled placeholder, not a verified figure — implementation
  must not proceed with a guessed number. The stronger model id remains
  entirely undecided, by design, per correction 10. No live provider call
  of any kind was made or needed for this documentation-only revision.
- Next action: Owner reviews `docs/plans/SLICE_6_PLAN.md` v2. After
  explicit implementation approval and the model-switch confirmation to
  Sonnet, implementation may begin per the plan's section 5 build order
  (llm.py/drafting.py/models.py core, then eval.py/routing.py, then DB/
  route/UI wiring, then the section 6 verification). Do not implement
  until then.

## 2026-08-01 — Slice 6 plan corrected to v3 (planning only)

- Contributor/environment: SDE 1 / Claude Code
- Slice: Slice 6 (evaluation and cost-aware routing) — planning only, v3
- Role: Planner / correction implementer
- Implementation status: Not started (plan under owner review)
- Changes and corrections: Applied five further owner-approved SDE 2 review
  findings against v2 (`cc2c23c`) to `docs/plans/SLICE_6_PLAN.md`, recorded
  in a new section 0.2 alongside the preserved v1->v2 history in section
  0.1. (1) Corrected a real gap in v2's usage accounting: v2's population
  rule said a transport failure or non-2xx response produced no `TokenUsage`
  record at all, which meant such an attempt would silently vanish from the
  usage list and could then be miscounted by the aggregation logic as "no
  calls were made" (a known zero) rather than "a call was made whose outcome
  is unknown." v3 makes every issued HTTP attempt -- transport failure,
  non-2xx response, malformed/non-JSON HTTP 200, or a 200 with missing/
  malformed usageMetadata -- produce exactly one TokenUsage record via a
  single shared, best-effort `_extract_usage` helper called on every
  response received (checking even error-response bodies for authoritative
  usageMetadata, in case a provider ever includes it), with all four count
  fields None when nothing usable is found. `cost_breakdown == []` /
  `cost_tokens == 0` / `estimated_cost_microusd == 0` is now reserved
  strictly for a workflow that issued zero Gemini requests (no workspace
  key at all) -- the `_call_gemini`/`generate_structured_with_usage` design
  was reworked so every raised `LLMError` always carries the failed
  attempt's TokenUsage via its existing `.usage` attribute, and known usage
  from attempts preceding a later failure is preserved in call order. (2)
  Removed the separate `"thinking"` rate from
  `PRICING_USD_PER_MILLION_TOKENS` -- Google prices output inclusive of
  thinking tokens for these tool-free structured-output requests -- and
  corrected the dollar formula to `round(promptTokenCount x input_rate) +
  round((totalTokenCount - promptTokenCount) x output_rate)`, requiring
  known non-negative `promptTokenCount`/`totalTokenCount` with
  `totalTokenCount >= promptTokenCount`, defensively re-validated at
  pricing time independent of what population already enforced (the same
  "second independent check" discipline `scoring.assert_grounded` uses).
  `candidatesTokenCount`/`thoughtsTokenCount` remain stored on `TokenUsage`
  for visibility but are no longer read by the pricing function at all. As
  a deliberate, explicitly flagged refinement, `cost_tokens` (the token
  count) and `estimated_cost_microusd` (the dollar estimate) are now
  independently nullable rather than force-coupled, since a token count and
  a token price are different pieces of information with different
  requirements -- flagged in section 8 for the owner to simplify back to
  full coupling if preferred. (3) Replaced v2's "an absent
  `thoughtsTokenCount` key means a known zero" rule, which the review
  identified as an unsafe assumption, with: unknown by default, unless
  prompt, candidates, and total are all known and `total >= prompt +
  candidates`, in which case thinking is derived as the non-negative
  difference (naturally zero at the `total == prompt + candidates`
  boundary) -- otherwise (any field unknown, or an internally inconsistent
  `total < prompt + candidates` report) thinking stays unknown. `TokenUsage`
  gains a `thinking_tokens_derived: bool` field so the persisted breakdown
  can always distinguish a value the provider actually reported from one
  this codebase computed. (4) Fixed a genuine API contradiction: v2's
  `route_and_draft(brief, target, settings) -> RoutingOutcome` never
  received a `workspace_id`, yet its escalation-eligibility step called
  `db.get_paid_tier_enabled(workspace_id)` -- code that could not have
  worked as drafted. `route_and_draft` now takes an explicit
  `paid_tier_enabled: bool` keyword-only argument and the plan states
  plainly that `routing.py` performs no database access of any kind;
  `main.py`'s `create_draft` route now explicitly resolves
  `db.get_paid_tier_enabled(workspace_id)` using the request's own already-
  scoped `workspace_id` before calling routing, keeping the tenant-scoping
  guarantee anchored at the one call site that actually has a workspace
  identity in scope. (5) Corrected Gemini's authentication transport: the
  code as shipped since Slice 2 (and carried through v1/v2 unexamined)
  sends the API key as a `?key=` query parameter; since Slice 6 already
  refactors `_call_gemini` for the usage-measurement and model-selection
  changes above, this correction folds in switching to an `x-goog-api-key`
  request header in the same refactor, matching the exact pattern Slice 5
  already established for Apify (`Authorization: Bearer`) and YouTube
  (`X-goog-api-key`) -- `_url(model)` now returns a query-string-free URL,
  the existing `params={"key": api_key}` is removed from the httpx call
  entirely, and v2's "out of scope, not undertaken now" note for this exact
  fix is removed from section 2 since it is now in scope. Every one of the
  five corrections has new, explicitly named acceptance criteria in the
  revised section 6 (32 items total, up from 22), including the exact new
  tests the owner's instruction enumerated: no-request-issued-is-known-zero,
  transport-failure-produces-unknown, non-2xx-unless-authoritative-usage,
  malformed-200-preserves-earlier-known-attempts, missing/malformed-
  usageMetadata-is-unknown, ordered retry-usage preservation, the corrected
  prompt/output pricing formula, thoughtsTokenCount-not-auto-zero plus its
  exact derived-zero/derived-difference/unknown boundaries, `main.py`
  passing a workspace-scoped `paid_tier_enabled` into routing, routing
  performing zero database lookups, the Gemini key traveling only via the
  `x-goog-api-key` header, request URLs/query parameters carrying no
  credential, and sanitized errors/audit details/cost breakdowns never
  exposing the key or headers. Every v2 decision the owner asked to
  preserve was carried forward unchanged: strict workspace-key-only
  behavior with no environment fallback; `HIGH_FIT_THRESHOLD = 85` and
  `CONFIDENCE_THRESHOLD = 80`, both inclusive; the dedicated
  `workspace.paid_tier_enabled` column, default off; the LLM judge with its
  fully specified deterministic rubric fallback; per-attempt retry
  accounting; terminal invalid-key behavior; atomic draft/eval/cost/audit
  persistence; the SQLite-enforced one-eval-per-draft constraint; "estimated
  paid list-price" wording; the no-paid-live-verification-without-
  authorization rule; and the explicit statement that Slice 6 cannot be
  marked complete until the stronger model is owner-approved and passes its
  verification gate.
- Files or areas affected: `docs/plans/SLICE_6_PLAN.md` (rewritten, v2 ->
  v3), `collaboration.md` (handoff + recent activity), and this history
  entry. No application code, tests, templates, styles, seeds, schema, or
  dependency files were touched.
- Verification: Documentation-only change; no app code was written or run.
  The 212-test Slice 5 baseline is unchanged and was re-confirmed passing
  both before this revision began and again immediately before the commit.
  `git diff --check` passes on the three changed files. A credential-shaped-
  string scan (API-key/token/Bearer/query-parameter patterns) across the
  three changed files found no matches. Confirmed via `git status` that
  only `docs/plans/SLICE_6_PLAN.md`, `collaboration.md`, and
  `docs/history/COLLABORATION_LOG.md` are staged, and that the working tree
  is clean immediately after the commit.
- Last known working state: `codex/sde-1-slice-2-hardening` at `b640b49`;
  the application is unchanged at the Slice 5 completion state. Only these
  three documentation files differ from that baseline.
- Known limitations: Every numeric pricing constant in the plan remains an
  explicit, labelled placeholder, not a verified figure -- implementation
  must not proceed with a guessed number. The stronger model id remains
  entirely undecided, by design. The plan's thoughtsTokenCount-derivation
  rule and its independent-unknown-ness treatment of `cost_tokens` versus
  `estimated_cost_microusd` are both flagged in the plan's own section 8 as
  interpretations the owner may want to confirm, adjust, or simplify before
  implementation. No live provider call of any kind was made or needed for
  this documentation-only revision.
- Next action: Owner reviews `docs/plans/SLICE_6_PLAN.md` v3. After
  explicit implementation approval and the model-switch confirmation to
  Sonnet, implementation may begin per the plan's section 5 build order
  (llm.py's header-auth-plus-usage refactor, drafting.py's widened
  DraftResult, and models.py first, then eval.py/routing.py, then DB/route/
  UI wiring, then the section 6 verification). Do not implement until then.

## 2026-08-01 — Slice 6 plan corrected to v4 (planning only)

- Contributor/environment: Codex / SDE 2 in the shared Outpost workspace.
- Slice: Slice 6 — evaluation and cost-aware routing.
- Role: Implementation reviewer and owner-authorized correction implementer.
- Implementation status: Planning only. No Slice 6 application code, tests, schema, templates, styles, seeds, or dependencies were changed.
- Changes and corrections: Applied the final three review corrections against v3 (`4026021`). Invalid Gemini credentials are now terminal after every model-backed routing stage: default draft, default eval, escalated draft, and escalated eval; each stage has an explicit retained call-count/fallback case and preserves accumulated usage. Replaced the default-model pricing placeholders with the official `gemini-3.6-flash` paid list prices verified on 2026-08-01 ($1.50 per million input tokens and $7.50 per million output tokens, with thinking included in output). Replaced binary-float and component-wise rounding with string-constructed `Decimal` rates, exact per-attempt accumulation, and one final `ROUND_HALF_UP` to integer micro-USD. Preserved the approved independently nullable `cost_tokens` and `estimated_cost_microusd` semantics.
- Files or areas affected: `docs/plans/SLICE_6_PLAN.md`, `collaboration.md`, and this history entry only.
- Verification: `git diff --check` passed; the changed-file list contained documentation only; targeted stale-placeholder and credential-pattern scans returned no matches; `python -m unittest discover -s tests` passed all 212 retained tests. No live or paid provider call was made.
- Last known working state: Branch `codex/sde-1-slice-2-hardening`; application baseline remains `b640b49` at the completed Slice 5 state. The v4 plan is based on v3 planning commit `4026021`.
- Known limitations: The stronger escalation-model id and its pricing remain deliberately owner-gated and unverified. Slice 6 cannot be marked complete against `SPEC.md` until the owner approves that model and the required safe verification gate passes. The `thoughtsTokenCount` derivation remains an explicitly documented assumption for optional safe verification.
- Next action: Owner performs final review of `docs/plans/SLICE_6_PLAN.md` v4. Do not begin Slice 6 implementation until the owner explicitly approves the plan and confirms the required model switch.

## 2026-08-01 — Slice 6 implemented: evaluation and cost-aware routing

- Contributor/environment: Claude Code / SDE 1, running in a Claude Code
  worktree session (`outpost-slice-6-impl-066cf9`) whose assigned working
  directory did not match this task's target branch/workspace; per this
  session's own worktree-mismatch check, all edits were made directly
  against the correct main working tree (`codex/sde-1-slice-2-hardening`,
  starting commit `f052a10`) rather than the stale bound worktree, using
  absolute paths and explicit `cd`-prefixed shell commands throughout.
- Slice: Slice 6 (evaluation and cost-aware routing) — full implementation,
  per owner-approved `docs/plans/completed/SLICE_6_PLAN.md` v4.
- Role: Implementer.
- Implementation status: Complete against the plan's own scope. **Not**
  complete against `SPEC.md` §6 — `ESCALATION_MODEL` remains owner-gated
  and unset; see Known limitations below.
- Changes and corrections: Implemented the plan end to end. New:
  `app/agent/eval.py` (`evaluate_draft`, `EvalOutcome`/`EvalStatus`, the
  fully-specified four-dimension deterministic heuristic rubric reusing
  `drafting._recipient_identity`/`_norm_for_substring`/`_parse_fit_reasons`/
  `BANNED_FILLER_PHRASES` rather than duplicating them), `app/agent/
  routing.py` (`route_and_draft`, `RoutingOutcome`, `_price`,
  `PRICING_USD_PER_MILLION_TOKENS`, `HIGH_FIT_THRESHOLD`/
  `CONFIDENCE_THRESHOLD`, `ESCALATION_MODEL = None`; takes
  `paid_tier_enabled` as an explicit argument and performs zero database
  access), `tests/test_slice6_eval_routing.py` (51 tests). Modified:
  `app/llm.py` (`_resolve_key` is strictly `settings.get("gemini")`, `os`
  import removed; `TokenUsage`/`MeasuredResult` dataclasses;
  `_extract_usage`/`_derive_thinking` called on every received response
  before any status check; `generate_structured_with_usage` accumulates
  usage across the two-shot retry; `generate_structured` becomes a thin
  wrapper; `_call_gemini` sends the key only via the `x-goog-api-key`
  header against a query-string-free `_url(model)`), `app/agent/
  drafting.py` (`BANNED_FILLER_PHRASES` constant; `DraftResult.usage`;
  `draft_outreach`'s new `model` parameter threaded to
  `generate_structured_with_usage`, so it now calls that instead of
  `generate_structured`), `app/models.py` (`EvalDimension`/`EvalRubric`/
  `EvalResult`, the last enforcing score-equals-sum-of-dimensions),
  `app/db.py` (`_add_column_if_missing` helper; idempotent
  `workspace.paid_tier_enabled`/`draft.cost_breakdown_json`/
  `draft.estimated_cost_microusd` migrations; the `eval` table
  (`draft_id UNIQUE`); `get_paid_tier_enabled`/`set_paid_tier_enabled`;
  atomic `create_draft_with_routing` writing the draft, its cost columns,
  its eval row, and `draft.created`/`eval.scored`/routing-decision audit
  rows in one transaction; `EvalAlreadyExists`; `get_eval_for_draft`;
  `outreach_cost_summary`; `list_pending_drafts`/`list_pipeline_targets`
  extended with LEFT JOINed eval/cost columns), `app/audit_banners.py`
  (namespaced `eval.scored`/`routing.*` action constants and labels, an
  `eval_detail` helper, and `ROUTING_ACTION_FOR` mapping routing_action ->
  audit action, with `"default"` intentionally mapping to no audit row),
  `app/main.py` (`create_draft` now resolves `paid_tier_enabled` once and
  calls `routing.route_and_draft` then `db.create_draft_with_routing`;
  `_cost_display`/`_eval_dimensions` helpers; Approvals/Pipeline/campaign-
  detail routes pass eval score, cost display, and — on Approvals — a
  running cost-per-outreach summary; Settings resolves/saves the paid-tier
  opt-in), and four templates (`approvals.html` — cost summary strip, model/
  eval/cost per draft card, an expandable rubric; `pipeline.html` — eval
  score and cost per card; `campaign_detail.html` — eval score and cost per
  row where a draft exists; `settings.html` — the paid-tier checkbox and a
  corrected Gemini key hint with no `GEMINI_API_KEY` reference), plus new
  `.cost-summary`/`.checkbox-field`/`.draft-card__meta`/`.pl-card__meta`/
  `.target-cta-cost` CSS rules, all built from existing design tokens only.
  One necessary, mechanical deviation beyond the plan's own file list:
  `tests/test_slice4_drafting.py` (9 tests) had its Gemini-call mock target
  changed from `app.agent.drafting.llm.generate_structured` to
  `app.agent.drafting.llm.generate_structured_with_usage` (wrapping return
  values in `llm.MeasuredResult`), since `draft_outreach` now calls the
  latter directly to capture usage — every existing assertion and test
  scenario is unchanged; only the mock plumbing was updated to match the
  plan's own required internal call-site change. Without this, those nine
  tests would have silently stopped exercising their mocks and made live,
  unmocked HTTP calls to Gemini with a fake key during every test run
  (confirmed empirically before the fix: the tests still passed by
  accident on stale assertions while real "API key not valid" responses
  came back from the real endpoint) — a violation of the no-live-call
  testing discipline this fix restores.
- Files or areas affected: `app/agent/eval.py` (new), `app/agent/
  routing.py` (new), `app/llm.py`, `app/agent/drafting.py`, `app/models.py`,
  `app/db.py`, `app/audit_banners.py`, `app/main.py`,
  `app/templates/approvals.html`, `app/templates/pipeline.html`,
  `app/templates/campaign_detail.html`, `app/templates/settings.html`,
  `app/static/css/app.css`, `tests/test_slice6_eval_routing.py` (new),
  `tests/test_slice4_drafting.py`, `PROGRESS.md`, `DECISIONS.md`,
  `collaboration.md`, this file, and `docs/plans/completed/SLICE_6_PLAN.md`
  (moved from `docs/plans/SLICE_6_PLAN.md` with an updated status header;
  content otherwise unchanged). No `requirements.txt` change.
- Verification: `python -m unittest discover -s tests` passes 263/263
  (212 baseline + 51 new `test_slice6_eval_routing` tests), covering every
  plan §6 acceptance criterion (1-32) plus heuristic-rubric boundary cases,
  mocked at the `httpx.post`/`app.llm.generate_structured_with_usage`
  boundary — no real provider call, no real key. `git diff --check` passed
  (only pre-existing LF/CRLF autocrlf warnings, no errors). `git status`
  confirmed only the files listed above changed; no `requirements.txt`,
  seed, or unrelated file was touched. A credential-pattern scan
  (API-key/token/private-key regexes) over the complete diff found no
  matches; two synthetic test fixture strings that superficially resembled
  a Stripe-style `sk-` key prefix were renamed to unambiguous placeholders
  before this scan to avoid a future automated secret-scanner false
  positive. Live-verified against the real `outpost.db` in the correct
  working tree (not a script, not the owner's data touched destructively):
  started `uvicorn` on port 8010, created one new workspace ("Slice 6 UI
  Verify"), ran a business campaign end to end with zero keys configured
  (heuristic drafting/eval path), and confirmed via `curl` that Settings
  renders the paid-tier checkbox, Approvals shows "Model: heuristic",
  "Eval 100", "0 tokens (heuristic, no cost)", and a correct "~$0.0000"
  cost-summary average; approved the draft and confirmed Pipeline shows the
  same eval/cost figures; confirmed campaign detail shows the eval badge,
  cost line, and an Activity feed with "Draft evaluated"/"Draft created"
  (and correctly no "Routed..." row, since the no-key path's routing_action
  is `"default"`, which writes no extra audit row by design). No errors in
  the server log across this flow. This new workspace was left in place as
  normal product usage, matching the precedent set by Slice 2's and Slice
  5's own verification sessions (never reset/deleted). No live or paid
  Gemini/Apollo/Apify/YouTube call was made or authorized.
- Last known working state: `codex/sde-1-slice-2-hardening`, working tree
  clean except for the Slice 6 changes described above, ready to commit.
  All 263 tests pass.
- Known limitations: `ESCALATION_MODEL` is owner-gated and unset — the
  escalation tier is fully implemented and mocked-tested but dormant, and
  Slice 6 is not marked complete against `SPEC.md` §6 until the owner
  approves a specific stronger Gemini model id and it passes a safe,
  bounded live verification gate (no paid live verification was performed
  or authorized this session). The `thoughtsTokenCount`-derivation rule in
  `app/llm.py`'s `_derive_thinking` remains this plan's own interpretation,
  unconfirmed against a real Gemini response. The LLM judge always runs on
  the default model, never the escalation model, per plan §5.3. Re-
  evaluating a human-edited draft body remains out of scope (SPEC.md §4.8).
- Next action: Owner review of this implementation. If/when the owner
  wants the escalation tier active, approve a specific stronger Gemini
  model id so it can be safely, boundedly verified per the completed
  plan's §6 "Safe live verification," then Slice 6 can be marked complete
  against `SPEC.md`.

## 2026-08-01 — Slice 6 implementation review corrected: five findings

- Contributor/environment: Claude Code / SDE 1, running in a Claude Code
  worktree session whose assigned working directory again did not match
  this task's target branch/workspace (the same mismatch as the prior
  Slice 6 implementation session). Per the same worktree-mismatch check,
  all edits were made directly against the correct main working tree
  (`codex/sde-1-slice-2-hardening`, starting commit `d7f2cc8`) using
  absolute paths and explicit `cd`-prefixed shell commands.
- Slice: Slice 6 (evaluation and cost-aware routing) — implementation
  review corrections, owner-directed, against the completed
  `docs/plans/completed/SLICE_6_PLAN.md` v4.
- Role: Implementer.
- Implementation status: Complete for all five findings. Slice 6 remains
  **not** complete against `SPEC.md` §6 — `ESCALATION_MODEL` stays owner-
  gated and unset; unchanged by this pass.
- Changes and corrections, one per finding:
  1. **Concurrent-generation spend.** Two simultaneous "Draft outreach"
     requests for the same target could both reach
     `routing.route_and_draft` (both incurring real Gemini usage) before
     the pre-existing `one_active_draft_per_target` unique index caught
     the loser only at persistence time, after both had already paid for
     generation. Added `app/db.py`'s `draft_generation` table
     (`UNIQUE(workspace_id, target_id)`, `expires_at` TTL),
     `try_acquire_draft_generation`/`release_draft_generation`, and
     `GenerationInProgress`. `app/main.py`'s `create_draft` now acquires a
     reservation immediately after the existing active-draft UX check and
     before any Gemini call, wraps the entire campaign/brief/settings/
     routing/persistence sequence in a `try`, and releases the reservation
     in a `finally` regardless of outcome — a crashed process (finally
     never runs) is bounded by the 300-second TTL, not left blocking the
     target forever. The acquire/release transactions are each a single
     fast DELETE-then-INSERT or DELETE, committed immediately; no
     transaction is held open across a network call. A second concurrent
     request that loses the race is redirected to the campaign page rather
     than attempting generation at all.
  2. **Escalation mislabeling on a failed/ungrounded escalated draft.**
     `routing.route_and_draft` previously proceeded to evaluate and label
     `"escalated"` any escalated draft that wasn't specifically
     `INVALID_GEMINI_KEY` — including a plain provider error
     (`GEMINI_ERROR`) or a schema-valid-but-ungrounded response that had
     already fallen back to the heuristic (`HEURISTIC_FALLBACK`) one level
     down, silently presenting a heuristic body as an upgrade and wasting
     an eval call judging it. Added a
     `if escalated_draft.status != DraftStatus.LLM_OK` branch (after the
     existing `INVALID_GEMINI_KEY` check, which is unchanged) that keeps
     the already-valid default draft/eval, preserves the failed attempt's
     usage in `cost_breakdown`, and returns a new `routing_action =
     "escalation_failed"` with `routing_detail` carrying the real status
     and sanitized reason (e.g. `"gemini_error: provider boom"`). No
     escalated-body eval call is made in this branch.
  3. **Pricing-gated escalation.** Escalation eligibility previously
     checked only `ESCALATION_MODEL is None`, meaning setting the model id
     alone — with no corresponding entry in
     `PRICING_USD_PER_MILLION_TOKENS` — would have let a live call through
     with no way to price it. Added `routing._escalation_ready()`,
     requiring both a non-empty `ESCALATION_MODEL` and a `PRICING_USD_
     PER_MILLION_TOKENS[ESCALATION_MODEL]` entry whose `input`/`output`
     are both `Decimal` instances; step 4's eligibility check now calls
     this instead of the bare `is None` check.
  4. **Approvals cost-summary visibility.** `app/templates/approvals.html`
     previously nested the entire cost-summary block inside
     `{% if drafts %}` (the pending/edited queue), even though
     `cost_summary` is computed from every draft ever created in the
     workspace (`db.outreach_cost_summary`) — a workspace with only
     historical approved/rejected drafts and an empty pending queue showed
     no summary at all. It also nested the unknown-cost "excluded" badge
     inside `{% if cost_summary.known_cost_count > 0 %}`, so an
     all-unknown-cost workspace (zero known-cost drafts) never showed the
     excluded count either. Restructured to gate the whole block on
     `cost_summary.draft_count > 0` (independent of the pending queue) and
     moved the excluded-count badge outside the known-cost conditional so
     it always renders whenever `unknown_cost_count > 0`. No wording
     changed: "estimated paid list-price cost" and the heuristic
     zero-cost phrasing are unchanged.
  5. **SPEC.md accuracy.** Replaced "Reads the workspace LLM key or falls
     back to the free Gemini tier" (stale since Slice 6 removed the
     `GEMINI_API_KEY` environment fallback and there was never a "free
     Gemini tier" as such) with an accurate description: model calls use
     only the workspace's own saved Gemini key, and no key means the
     deterministic local heuristic/demo path, not a model call.
- Files or areas affected: `app/db.py` (`draft_generation` table,
  `try_acquire_draft_generation`, `release_draft_generation`,
  `GenerationInProgress`, `DRAFT_GENERATION_TTL_SECONDS`), `app/main.py`
  (`create_draft`'s reservation acquire/release), `app/agent/routing.py`
  (`_escalation_ready`, the `escalation_failed` branch, updated module/
  field docstrings), `app/audit_banners.py` (`ROUTING_ESCALATION_FAILED`,
  `ROUTING_ACTION_FOR["escalation_failed"]`, its `ACTION_LABELS` entry),
  `app/templates/approvals.html` (cost-summary restructure),
  `tests/test_slice6_eval_routing.py` (18 new tests: `_escalation_enabled`
  helper plus `DraftGenerationReservationTests`,
  `EscalationFailurePreservesDefaultTests`,
  `EscalationRequiresPricingTests`, `ApprovalsCostSummaryTests`; seven
  pre-existing tests' `ESCALATION_MODEL`-only patches were also updated to
  the new `_escalation_enabled()` helper so they keep exercising the
  escalation path now that pricing is required too — no assertion or
  scenario changed), `SPEC.md`, `PROGRESS.md`, `DECISIONS.md`,
  `collaboration.md`, and this file.
- Verification: `python -m unittest discover -s tests` passes 281/281
  (263 baseline plus 18 new), all mocked at the `httpx.post`/`app.llm.
  generate_structured_with_usage` boundary — no real provider call, no
  real key, no live Gemini/paid-provider call of any kind. The new
  concurrency test (`test_concurrent_requests_only_one_generates`) uses
  two real threads racing against a shared temp-file SQLite database (not
  `:memory:`) with a mocked, artificially slowed `routing.route_and_draft`
  and confirms the mock is invoked exactly once and the loser produces no
  pending draft; a companion test confirms a failed generation (a raised
  exception from the mocked routing call) still releases the reservation
  so the target is not permanently blocked; a third confirms the acquire
  transaction itself does not hold a database-wide write lock (an
  unrelated `create_workspace` call succeeds immediately after an acquire
  returns). `git diff --check` passed (only pre-existing LF/CRLF autocrlf
  warnings). `git status` confirmed only `SPEC.md`, `app/agent/routing.py`,
  `app/audit_banners.py`, `app/db.py`, `app/main.py`,
  `app/templates/approvals.html`, and `tests/test_slice6_eval_routing.py`
  changed (plus the four documentation files and this log, added in the
  same commit) — no unrelated file, seed, or `requirements.txt` change. A
  credential-pattern scan (API-key/token/private-key/`x-goog-api-key`-
  value regexes) over the complete diff found no matches. `ESCALATION_MODEL`
  was confirmed still `None` by direct import after all changes. Live-
  verified against the real `outpost.db` in the correct working tree (not
  a script; normal product usage through the running app, same precedent
  as prior sessions): started `uvicorn` on port 8011, created a new
  workspace ("Slice 6 Findings Verify"), ran a business campaign with zero
  keys configured, drafted and approved one target and drafted and
  rejected a second (producing a workspace with historical approved/
  rejected drafts and an empty pending queue), and confirmed via `curl`
  that the corrected `/approvals` page shows both the cost-summary
  ("~$0.0000") and the "No drafts waiting for review" empty state
  simultaneously — the exact scenario finding 4 was about. No errors in
  the server log across this flow. The `.cost-summary`/`.badge--muted` CSS
  classes touched by this fix are unchanged from the initial Slice 6
  implementation (already verified against light/dark theme tokens in
  that session); no new CSS was introduced by this pass, so no new visual
  regression is possible from this change. This new workspace was left in
  place as normal product usage, matching prior-session precedent (never
  reset/deleted).
- Last known working state: `codex/sde-1-slice-2-hardening`, working tree
  clean except for the changes described above, ready to commit. All 281
  tests pass.
- Known limitations: Unchanged from the initial implementation —
  `ESCALATION_MODEL` remains owner-gated and unset; the escalation tier is
  fully implemented and mocked-tested but dormant. The
  `thoughtsTokenCount`-derivation rule and the eval judge always running
  on the default model are both unaffected by this pass. The
  `draft_generation` reservation's 300-second TTL is a judgment call
  (comfortably above the worst-case 8-attempt/30s-timeout envelope) that
  the owner may want to tune once real generation latencies are observed.
- Next action: Owner review of the five corrections. If/when the owner
  wants the escalation tier active, approve a specific stronger Gemini
  model id and its verified pricing so it can be safely, boundedly
  verified per the completed plan's §6, then Slice 6 can be marked
  complete against `SPEC.md`.

## 2026-08-01 — Slice 6 implementation review corrected: two further findings

- Contributor/environment: Claude Code / SDE 1, running in a Claude Code
  worktree session whose assigned working directory again did not match
  this task's target branch/workspace (the same recurring mismatch as
  both prior Slice 6 sessions). All edits were made directly against the
  correct main working tree (`codex/sde-1-slice-2-hardening`, starting
  commit `099fc67`) using absolute paths and explicit `cd`-prefixed shell
  commands, per the same verified workaround.
- Slice: Slice 6 (evaluation and cost-aware routing) — a second
  implementation-review correction pass, owner-directed, against the
  completed `docs/plans/completed/SLICE_6_PLAN.md` v4 and the prior
  correction commit `099fc67`.
- Role: Implementer.
- Implementation status: Complete for both findings. Slice 6 remains
  **not** complete against `SPEC.md` §6 — `ESCALATION_MODEL` stays
  owner-gated and unset; unchanged by this pass.
- Changes and corrections, one per finding:
  1. **Reservation acquisition was not tenant-scoped.**
     `db.try_acquire_draft_generation(workspace_id, target_id)` inserted
     the caller-supplied `workspace_id`/`target_id` pair directly into
     `draft_generation`. SQLite's foreign-key constraints prove each id
     independently references a real row, but nothing previously proved
     the referenced target actually belonged to the supplied workspace —
     a caller passing a mismatched (workspace_id, target_id) pair (or a
     target_id that doesn't exist) could still have inserted a
     reservation row, purely because the acquiring statement never
     joined against `target` to check ownership. Fixed by changing the
     acquiring INSERT to `INSERT INTO draft_generation (workspace_id,
     target_id, expires_at) SELECT ?, target.id, datetime('now', ?) FROM
     target WHERE target.workspace_id = ? AND target.id = ?` — the exact
     `INSERT ... SELECT` idiom `add_draft` already uses for the same
     tenancy guarantee. When the WHERE clause matches no row (a
     nonexistent target, or a target belonging to a different
     workspace), the INSERT affects zero rows; the function now checks
     `cursor.rowcount == 0` after the insert attempt and returns `None`
     in that case, identical to the pre-existing "already reserved"
     rejection path, so callers don't need to distinguish the two. This
     is authoritative independent of any caller's own `get_target()`
     lookup, and does not change the transaction's shape: still one
     DELETE (reclaiming an expired row) plus one INSERT, committed
     immediately, never held open across a network call.
  2. **Pricing validation accepted any `Decimal`, including invalid
     ones.** `routing._escalation_ready()` previously only checked
     `isinstance(rates.get("input"), Decimal)` and the same for
     `"output"` — a zero, negative, `NaN`, or infinite `Decimal` all
     satisfied `isinstance`, so any of them would have let
     `_escalation_ready()` return `True` and a paid escalation call
     proceed with garbage pricing. Added `_is_valid_rate(value)`, which
     requires `isinstance(value, Decimal) and value.is_finite() and
     value > 0`, and `_escalation_ready()` now calls it for both
     `"input"` and `"output"`. The `is_finite()` check is written first
     and combined with `and` specifically so it short-circuits before
     the `> 0` comparison: Python's default `decimal` context traps
     `InvalidOperation` on a `NaN`/`Infinity` ordering comparison, so
     evaluating `value > 0` before confirming finiteness would raise
     instead of returning `False`.
- Files or areas affected: `app/db.py`
  (`try_acquire_draft_generation`'s INSERT and docstring),
  `app/agent/routing.py` (`_is_valid_rate`, `_escalation_ready`),
  `tests/test_slice6_eval_routing.py` (11 new tests: three DB-level
  tenant-ownership tests plus a request-path "routing never called on
  rejected acquisition" test in `DraftGenerationReservationTests`, and
  seven pricing-validation tests plus a routing-level assertion in
  `EscalationRequiresPricingTests`), `PROGRESS.md`, `DECISIONS.md`,
  `collaboration.md`, and this file.
- Verification: `python -m unittest discover -s tests` passes 292/292
  (281 baseline plus 11 new), all mocked at the `httpx.post`/`app.llm.
  generate_structured_with_usage` boundary — no real provider call, no
  real key, no live Gemini/paid-provider call of any kind.
  `test_acquire_rejects_a_target_belonging_to_another_workspace` and
  `test_acquire_rejects_a_missing_target` call
  `db.try_acquire_draft_generation` directly (not through the route) and
  confirm both a `None` return and zero rows left in `draft_generation`;
  a companion asserts the legitimately owning workspace can still
  acquire the same target normally afterward.
  `test_route_never_calls_routing_when_acquisition_is_rejected` calls
  `app.main.create_draft` directly with `db.try_acquire_draft_generation`
  mocked to return `None` and confirms `routing.route_and_draft` is never
  invoked. The pricing tests cover valid positive rates, a missing
  pricing entry entirely, a missing `input` or `output` key, four
  non-`Decimal` value types, three zero/negative values, and `NaN`/
  `Infinity`/`-Infinity` in both the `input` and `output` slot, plus one
  routing-level test confirming `Decimal("NaN")` pricing produces
  `routing_action == "escalation_unavailable"` with only the default
  draft/eval calls made (`gen.call_count == 2`) and no escalation attempt.
  `git diff --check` passed (only a pre-existing LF/CRLF autocrlf
  warning). `git status` confirmed only `app/agent/routing.py`,
  `app/db.py`, and `tests/test_slice6_eval_routing.py` changed for the
  code/test fix, plus `PROGRESS.md`, `DECISIONS.md`, `collaboration.md`,
  and this file for documentation — no unrelated file, template, seed, or
  `requirements.txt` change; no UI template was touched by this pass, so
  no browser/theme verification was needed. A credential-pattern scan
  (API-key/token/private-key regexes) over the complete diff found no
  matches. `ESCALATION_MODEL` was confirmed still `None` by direct import
  after all changes.
- Last known working state: `codex/sde-1-slice-2-hardening`, working tree
  clean except for the changes described above, ready to commit. All 292
  tests pass.
- Known limitations: Unchanged from both prior passes — `ESCALATION_MODEL`
  remains owner-gated and unset; the escalation tier is fully implemented
  and mocked-tested but dormant. The `draft_generation` reservation's
  tenant-scoping fix and the pricing validator's finite/positive
  requirement are both defense-in-depth corrections to code that had no
  known live exploitation path (the route's own `get_target()` call and
  the fact that only `gemini-3.6-flash`'s real, valid pricing entry
  exists today both already prevented practical harm) — they are
  correctness fixes for the underlying primitives, not evidence of an
  incident.
- Next action: Owner review of these two corrections. If/when the owner
  wants the escalation tier active, approve a specific stronger Gemini
  model id and its verified pricing so it can be safely, boundedly
  verified per the completed plan's §6, then Slice 6 can be marked
  complete against `SPEC.md`.
