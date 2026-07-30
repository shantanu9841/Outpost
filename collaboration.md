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
