# Outpost Progress and State

Read this at the start of every session. Update it at the end of every slice.

## Current state
Slice 1 done and committed. Two tables (`workspace`, `workspace_setting`) live in
`app/db.py`, both created idempotently on startup. The active workspace is tracked
in a plain cookie, resolved per-request by the `get_current_workspace` FastAPI
dependency — every route that touches tenant data depends on it and every db.py
function takes `workspace_id` as a required parameter (forgetting it is a
TypeError, not a silent leak). A workspace can be created (`/workspaces/new`) and
switched via a dropdown in the side rail. A settings page (`/settings`) lets the
owner paste and save youtube/apify/apollo/llm keys per workspace; saved keys
display masked (`••••` + last 4 chars) and can be removed. Verified end to end:
created "Workspace Alpha" and "Workspace Beta," saved different Apollo/YouTube
keys in each, confirmed each workspace's settings page shows only its own keys
(both through the UI and by querying `workspace_setting` directly), confirmed
switching workspaces preserves each one's saved keys, and confirmed Remove
deletes only the targeted key. Checked in both themes with no console errors.
One new dependency added: `python-multipart` (required by FastAPI for HTML form
parsing — logged in DECISIONS.md). Next action: Slice 2 (B2B discovery, Apollo).

## Slice checklist
- [x] Slice 0: Foundation (scaffold, git, styled shell, theme toggle)
- [x] Slice 1: Workspaces and BYO-key settings
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
