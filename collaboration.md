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
