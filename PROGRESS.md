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
both the Apollo and Gemini REST calls — logged in DECISIONS.md). Next action:
Slice 3 (fit-scoring with citations).

## Slice checklist
- [x] Slice 0: Foundation (scaffold, git, styled shell, theme toggle)
- [x] Slice 1: Workspaces and BYO-key settings
- [x] Slice 2: B2B discovery (Apollo)   [load skill: apollo:prospect, apollo:enrich-lead]
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
