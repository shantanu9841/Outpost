# Outpost Progress and State

Read this at the start of every session. Update it at the end of every slice.

## Current state
Not started. Files in place: CLAUDE.md, SPEC.md, DECISIONS.md, PROGRESS.md, design.md. Next action: Slice 0.

## Slice checklist
- [ ] Slice 0: Foundation (scaffold, git, styled shell, theme toggle)
- [ ] Slice 1: Workspaces and BYO-key settings
- [ ] Slice 2: B2B discovery (Apollo)   [load skill: apollo:prospect, apollo:enrich-lead]
- [ ] Slice 3: Fit-scoring with citations
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
