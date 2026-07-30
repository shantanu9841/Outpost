# Outpost Decision Log

Append-only. Newest at the bottom. Each entry records what we decided, why, and what we rejected. This is also raw material for writeups; each entry can become a post.

Format:
## Title
*YYYY-MM-DD*
Decision: ...
Why: ...
Rejected: ...

---

## Build one engine, not twelve projects
*2026-07-29*
Decision: Build a single outreach product that folds in six of the twelve viral "agentic projects" (structured output, RAG with citations, memory, human-in-the-loop, cost-aware routing, auto-eval), rather than twelve separate repos.
Why: The twelve share one skeleton. Six patterns in one real product is a stronger product-portfolio signal than twelve thin demos, and it suits a non-engineer showing product judgment over plumbing.
Rejected: Building all twelve. Padding, and the wrong audience for a PM.

## Domain-neutral public build, private instance for the real client
*2026-07-29*
Decision: The public portfolio version points at a neutral domain (functional wellness CPG). The same system, privately configured, serves the real client.
Why: Lets the work be shown off freely without tying the public profile to a restricted industry, and keeps the health-tech positioning coherent.
Rejected: Making the restricted-industry version the public piece. Platform rules and personal positioning both argue against it.

## Source-agnostic engine
*2026-07-29*
Decision: Discovery talks to a Source interface. YouTube, Apify, and Apollo are interchangeable sources. Adding one is a config change.
Why: One engine serves both creator outreach and B2B outreach, and it reads as deliberate system design. It also lets demo-safe free sources stand in for paid ones.
Rejected: Hardcoding one provider. Brittle and a weaker story.

## Apollo for B2B, not LinkedIn scrapers
*2026-07-29*
Decision: Use Apollo's licensed API for all business discovery, including the client's distributor and logistics hunt. No LinkedIn scrapers.
Why: LinkedIn scraping is against terms of service, gets accounts banned, breaks constantly, and is a liability rather than a credential. Apollo does the same job compliantly and is already connected.
Rejected: Third-party LinkedIn scrapers. Risk lands on the owner's own account, and the scraping is the least impressive and least reliable part.

## Creator data via a maintained paid API, not a self-hosted scraper
*2026-07-29*
Decision: Instagram and TikTok data comes from a maintained pay-as-you-go provider (Apify to start). YouTube's free API stays as fallback and demo-safety.
Why: A maintained API is the same build effort as the free path but more reliable, and a stronger "integrated a licensed provider" story. Self-hosting a scraper keeps the brittleness with us.
Rejected: Our own scraper (brittle, grey-market). Renting raw scraper code to self-host (brittleness stays ours).

## Zero cost to the builder via BYO-key and free tiers
*2026-07-29*
Decision: Every metered service is bring-your-own-key, pasted into workspace settings. Defaults use free tiers (YouTube, Gemini free tier). Hosting runs locally or on free tiers. Demo mode works with no keys via seed data.
Why: No tolerance for spend on something that might fail at the demo stage. BYO-key also happens to be correct multi-tenant design and hands running costs to the client from day one.
Rejected: Paying for shared keys or hosting up front. Unnecessary cost and a worse architecture.

## Cost-aware routing as a feature, not just a saving
*2026-07-29*
Decision: Draft with the free model by default, escalate to a paid model only for high-fit targets, early-exit on confidence, and show cost-per-outreach in the UI.
Why: Turns frugality into a demonstrable capability that few portfolios show, and keeps real-use cost low.
Rejected: Always calling the best model. Wasteful and invisible.

## Human approves every send
*2026-07-29*
Decision: The agent only drafts. A human edits, approves, or rejects every message, with a full audit trail. No auto-send, no auto-post.
Why: This is the trust and compliance core and the most product-relevant capability of the set. It also sidesteps platform posting restrictions.
Rejected: Autonomous sending. Higher risk, lower signal, and against platform rules for some sources.

## Stack: Python, FastAPI, SQLite, plain HTML and JS
*2026-07-29*
Decision: Fewest moving parts. No frontend framework, no Docker, no cloud dependency to run.
Why: Runs cleanly on the owner's Windows setup with no Hyper-V issue, is easiest to run and demo as a non-engineer, and Claude Code builds it reliably.
Rejected: Heavier stacks. More to break, no portfolio benefit for a data tool.

## Design system locked before build
*2026-07-29*
Decision: The visual system is defined in design.md (Linear and Vercel style, dense, light and dark) and followed exactly by the build.
Why: Design is judged in AI-built products. Locking tokens first prevents each session inventing its own look.
Rejected: Building the UI ad hoc. Incoherent result.

## Files written, not a paste-in prompt
*2026-07-29*
Decision: The plan and rules live as permanent files (CLAUDE.md, SPEC.md, DECISIONS.md, PROGRESS.md, design.md) that Claude Code reads each session, rather than a one-off prompt.
Why: Files are the persistent memory system and stay token-efficient across weeks. A prompt is spent the moment it runs and adds a translation layer the owner cannot scrutinize.
Rejected: A single paste-in setup prompt. Throwaway, and drifts from the spec unseen.

## Tenant isolation via explicit workspace_id parameter, not middleware
*2026-07-29*
Decision: Every function in app/db.py that reads or writes tenant data takes workspace_id as a required parameter, and every SQL statement inside it filters by it. No request-scoped middleware auto-injects the tenant id, and there is no global/ambient "current workspace" state on the server side.
Why: Forgetting to pass workspace_id is a TypeError at call time, caught immediately during development, instead of a silent cross-tenant data leak discovered later. It's also the simplest pattern to read and audit — a non-engineer can see the isolation boundary in every function signature.
Rejected: Middleware or a context-local variable that injects workspace_id automatically. Convenient, but the isolation guarantee becomes invisible at the call site and easy to bypass by accident.

## Active workspace tracked via cookie, not accounts
*2026-07-29*
Decision: Outpost has no login/authentication. The active workspace is tracked in a plain cookie (workspace_id), resolved per-request by a get_current_workspace dependency that falls back to the most recently created workspace if the cookie is missing or stale.
Why: This is a local, single-owner tool (SPEC.md), not a multi-user SaaS — the workspace is the tenant, not a logged-in user. A cookie is the simplest thing that lets "create and switch between workspaces" work without inventing an auth system out of scope for this build.
Rejected: A user-accounts/login system. Out of scope for a local single-owner tool and adds real complexity for no product benefit at this stage.

## New dependency: python-multipart
*2026-07-29*
Decision: Added python-multipart to requirements.txt.
Why: FastAPI requires it to parse HTML form submissions (Form(...) parameters), which Slice 1's workspace-create and settings-save routes use. Server-rendered HTML with plain form posts (per the stack decision) needs this to read the posted fields at all.
Rejected: Nothing rejected — this is a required transitive dependency for the chosen stack, not a design choice with alternatives.

## Every source returns one shared SourceResult contract
*2026-07-30*
Decision: Every Source implementation's `search()` returns the same `SourceResult` dataclass (candidates, status, source_attempted, source_used, sanitized reason) and never raises past its own boundary. `discover()` is the only place that decides whether and why to fall back to seed data.
Why: A live-Apollo test during Slice 2 planning exposed that the real free-tier key returns 403 on every search endpoint, and the first implementation attempt (v1, `slice-2-scratch`) treated that as a crash instead of a normal, handled outcome. Centralizing fallback logic in one place, with one uniform result shape, means adding a second live source later (Slice 5) can't reintroduce that bug independently.
Rejected: Letting each source raise its own exception type and having the caller catch and interpret them. Scales badly past one source and was the exact shape of the original bug.

## IntakeStatus distinguishes a rejected credential from every other failure
*2026-07-30*
Decision: `IntakeStatus` has four values — `LLM_OK`, `NO_GEMINI_KEY`, `INVALID_GEMINI_KEY`, `GEMINI_ERROR` — where `INVALID_GEMINI_KEY` is reserved strictly for a response Gemini's API itself identifies as a credential rejection (HTTP 403, or 400 with `INVALID_ARGUMENT` and an "API key" message). Everything else — network failure, timeout, other HTTP status, exhausted validation retry — is `GEMINI_ERROR`.
Why: Collapsing these into one "something went wrong with the key" status would tell the owner to check their Gemini key when the real problem might be a network blip or a transient 5xx, which is actively misleading advice. Confirmed live against the real API (see verification below) before relying on the distinction elsewhere.
Rejected: A single generic `INTAKE_ERROR` status. Simpler but loses information the UI can act on.

## Settings key renamed llm -> gemini
*2026-07-30*
Decision: The workspace setting previously named `llm` is renamed to `gemini`, with an idempotent startup migration (`UPDATE workspace_setting SET key_name = 'gemini' WHERE key_name = 'llm'`) that preserves any existing saved key.
Why: The code only ever calls Gemini's API — naming the setting `llm` implied a choice of provider that doesn't exist yet and would mislead the owner into thinking any LLM key works there.
Rejected: Keeping the generic `llm` name for future-proofing. Speculative; nothing in the current build supports a second LLM provider, and CLAUDE.md's Local data rule requires any such rename to preserve existing rows rather than assume a clean slate.

## New dependency: httpx
*2026-07-30*
Decision: Added httpx to requirements.txt.
Why: One HTTP client for both the Apollo REST calls (`app/sources/apollo.py`) and the Gemini REST calls (`app/llm.py`), with synchronous calls matching FastAPI's sync route handlers used so far.
Rejected: Nothing rejected — this is the natural choice for the stack already in place.

## Audit schema includes campaign_id from the start
*2026-07-30*
Decision: The `audit` table's schema, as first created, includes a nullable `campaign_id` column, and `list_audit(workspace_id, campaign_id)` filters directly on it.
Why: An earlier draft (v1) had no `campaign_id` column and instead inferred which audit rows belonged to a campaign by a time-window heuristic ("the two most recent rows near campaign creation"), which is fragile under any concurrent activity. Since this is the first version of the table ever shipped, there was no reason to ship the fragile version first and migrate later.
Rejected: The time-window heuristic. Confirmed fragile in review; no advantage over a real foreign key.
