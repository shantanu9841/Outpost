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
