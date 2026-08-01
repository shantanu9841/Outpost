# Outpost Product Spec

## 1. Overview
Outpost is a multi-tenant outreach command center. One business per workspace. A workspace owner describes what they are promoting; Outpost discovers relevant targets from swappable sources, scores each for fit with cited evidence, drafts personalized outreach, holds every draft for human approval, and tracks approved targets through a pipeline. It logs draft-quality scores and per-outreach cost.

Two target types, one engine:
- Creators: found via YouTube (free) and Instagram/TikTok (Apify, BYO key).
- Businesses: found via Apollo (BYO key). Used for distributor and logistics outreach.

The engine (intake, discovery, fit-scoring, drafting, approval, pipeline, memory, eval, routing) is identical across target types. Only the source changes. Building this as a genuine abstraction is a core goal, not an afterthought.

## 2. Architecture
- `app/main.py`: FastAPI app, routes, page rendering.
- `app/db.py`: SQLite connection, schema, migrations.
- `app/models.py`: Pydantic schemas for all structured data and all model outputs.
- `app/sources/`: one module per source behind a shared Source interface. Files: `base.py`, `youtube.py`, `apify.py`, `apollo.py`.
- `app/agent/`: `intake.py` (brief parsing), `scoring.py` (fit plus citations), `drafting.py` (outreach), `eval.py` (quality rubric), `routing.py` (model selection plus cost).
- `app/llm.py`: single wrapper for all model calls. Takes a schema, validates, retries, records token cost. Model calls use only the workspace's own saved Gemini key; with no key, the caller falls back to a deterministic local heuristic/demo path instead of calling a model.
- `app/templates/`: HTML templates styled per design.md.
- `app/static/`: CSS (design tokens) and minimal JS.
- `outpost.db`: the database file.
- `seeds/`: sample workspaces, targets, and drafts for demo mode.

## 3. Data model (SQLite)
Every table except `workspace` carries a `workspace_id`. Every query filters by it.

- `workspace`: id, name, created_at.
- `workspace_setting`: workspace_id, key_name (youtube, apify, apollo, llm), key_value, created_at. Stored locally, masked in the UI. This is a local single-owner tool, not production secret management; that is out of scope.
- `campaign`: id, workspace_id, promoting_what (raw text), brief_json (parsed brief), target_type (creator or business), created_at.
- `target`: id, workspace_id, campaign_id, source (youtube, apify, apollo), external_id, name, handle_or_domain, reach, raw_json, fit_score, fit_reasons_json (reasons with citations), stage (queued, contacted, replied, live, declined), created_at.
- `draft`: id, workspace_id, target_id, body, status (pending, approved, rejected, edited), edited_body, model_used, cost_tokens, created_at.
- `audit`: id, workspace_id, actor (human or agent), action, target_id, draft_id, detail, created_at.
- `eval`: id, workspace_id, draft_id, rubric_json, score, created_at.

## 4. The core loop
1. Intake: owner types what they are promoting. `intake.py` parses it into a structured brief (Pydantic): product, audience, tone, target_type, niche or industry, target countries. Validated, retried on bad parse.
2. Discovery: the matching source returns candidate targets into the `target` table for that campaign.
3. Fit-scoring: for each candidate, pull evidence (recent videos, company detail) and have the model return a fit score 0 to 100 plus reasons, each reason citing specific evidence. Validated structured output. No score without a citation.
4. Drafting: generate a personalized outreach draft that references the cited evidence. Routing picks the model.
5. Approval: draft lands in the queue as pending. Human edits, approves, or rejects. Every action written to `audit`. Nothing sends automatically.
6. Pipeline: an approved target moves through queued, contacted, replied, live, or declined on a board.
7. Memory: campaigns, targets, and past drafts persist. A new session reads existing state; the agent does not re-discover known targets.
8. Eval: after a draft is created, `eval.py` scores it against a rubric (personalization, specificity, non-genericness, clear ask). Score and rubric stored, surfaced in the UI.
9. Routing and cost: `routing.py` drafts with the cheap free model by default, escalates to a better model only for high-fit targets when an LLM key is present, early-exits when confident. `llm.py` records token cost per call. UI shows cost per outreach.

## 5. Sources (the Source interface)
Each source implements two methods: `search(brief) -> list of candidates` and `evidence(candidate) -> evidence blob`.
- `youtube.py`: YouTube Data API, free quota. Default creator source. Works without a key under the free quota; owner may paste a key to raise the quota.
- `apify.py`: Instagram and TikTok via Apify actors. Requires the workspace Apify key. Off unless a key is present. Confirm the current actor and its pricing before wiring.
- `apollo.py`: Apollo people and company search. Requires the workspace Apollo key. Business target source.
- Demo mode: if a source has no key, discovery serves seeded data from `seeds/` so the flow always completes.

## 6. Build order (slices)
Build in this order. Verify and commit each before starting the next.

### Slice 0: Foundation
Scaffold the repo. A FastAPI app that runs, SQLite connected, one health route, a base HTML layout wired to design.md tokens with a working light and dark toggle, requirements.txt, .gitignore, git initialized.
Done when: `uvicorn` runs, http://localhost:8000 shows a styled empty shell with a working theme toggle, and the repo has an initial commit.

### Slice 1: Workspaces and BYO-key settings
Workspace create and switch. A settings page per workspace to paste and save keys (youtube, apify, apollo, llm), stored in `workspace_setting`, masked on display. All later queries scoped by workspace_id.
Done when: two workspaces can be created and switched between, keys save and show masked, and data in one workspace is invisible in the other (verify with seeded rows).

### Slice 2: B2B discovery (Apollo)
An intake box that parses "what are you promoting" into a validated brief. Apollo implemented behind the Source interface. A campaign with target_type business calls Apollo and fills the discovery table with real companies (distributors, logistics) when an Apollo key is present, or seeded companies when not.
Done when: entering a brief for a business campaign returns a scannable discovery table of companies with name, domain, and size or reach, styled per design.md.
Load skill for this slice: apollo:prospect and apollo:enrich-lead.

### Slice 3: Fit-scoring with citations
For each discovered target, pull evidence and score fit 0 to 100 with reasons that cite specific evidence. Structured output validated, retry on bad parse, no score without at least one citation. Fit coloring per design.md (85 and above success, 70 to 84 default text, below 70 muted).
Done when: the discovery table shows a fit score and, on expand, cited reasons for each target, and a deliberately weak target scores low with honest reasons.

### Slice 4: Drafting, approval queue, pipeline
Generate a personalized draft per target selected for outreach, referencing the cited evidence. Drafts enter the approval queue as pending. Human edits, approves, or rejects; each action audited. Approved targets appear on a pipeline board (queued, contacted, replied, live, declined) with stage changes by button or drag.
Done when: a draft can be generated, edited, approved or rejected with the audit trail recording each step, and an approved target shows on the pipeline board. Nothing sends on its own.
Load skill for this slice: beautiful-prose and humanizer, applied to the drafting prompt so drafts read human, follow Mom Test directness, and avoid form-letter tone.

### Slice 5: Creator sources and demo mode
Implement `youtube.py` (free) and `apify.py` (BYO) behind the Source interface. A creator campaign discovers creators from YouTube, or Instagram and TikTok when an Apify key is present. Confirm demo mode end to end: with no keys at all, every step completes on seeded data.
Done when: a creator campaign runs start to finish on free YouTube, Apify activates when its key is present, and the whole app demos start to finish with zero keys via seed data.

### Slice 6: Eval and cost-aware routing
`eval.py` scores each draft against a rubric and stores it. `routing.py` drafts with the free model by default, escalates to a paid model only for high-fit targets when an LLM key is present, and early-exits on confidence. `llm.py` records token cost per call. The UI shows cost per outreach and an eval score per draft.
Done when: each draft shows an eval score, the model used is visible, high-fit targets route to the better model only when a key exists, and a running cost-per-outreach figure displays.

## 7. Out of scope (do not build)
Payments, creator payouts, Stripe. Auto-posting or publishing to any platform. Real message send integration (email or DM sending) beyond marking a target as contacted. Any scraper hosted by us. A frontend framework. Production secret management.
