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

## Apollo status classification separates rate-limits and provider errors from credential problems
*2026-07-30*
Decision: `SourceStatus` grew three values beyond Slice 2's original set — `RATE_LIMITED` (Apollo 429), `PROVIDER_ERROR` (Apollo 5xx, 422, or any other unexpected non-200, and a malformed HTTP 200 payload), and `SEED_ERROR` (the local seed fallback itself failed to load). Only a 401 maps to `INVALID_KEY`; a 403 stays `INSUFFICIENT_PLAN`.
Why: The original Slice 2 implementation collapsed every non-200/401/403 response into `INVALID_KEY`, which would tell an owner to replace a perfectly good key when Apollo was actually throttling them or having a bad day on its own infrastructure. That is actively misleading advice, and the failure mode is genuine — Apollo documents 429s, and 5xx/422 are ordinary provider realities. Each status now has banner copy that matches the real cause (wait and retry vs. this is Apollo's side, not yours vs. check your key), so the owner is never misdirected.
Rejected: Keeping a single generic non-200 bucket. Simpler, but it actively misinforms the person reading the banner — worse than no message at all.

## discover() never claims seed data was shown when the seed fallback itself fails
*2026-07-30*
Decision: If a live source fails and the seed fallback used to paper over that failure also fails (missing/invalid/misshaped seed file), `discover()` returns `SEED_ERROR` with zero candidates and a combined explanation, rather than returning `SourceStatus.OK`-shaped seed data that doesn't actually exist.
Why: The whole point of the fallback design (from Slice 2) is that campaign-detail always shows what happened and why. A fallback-of-a-fallback failure is rare but real (a corrupted or missing `seeds/companies.json`), and silently reporting "seed data" when there is none would violate the same "never a silent fallback" principle the original discover() design was built around.
Rejected: Letting `SeedSource.search()` raise on failure and letting that exception propagate. Violates the Source "never raises" contract and would turn a data problem into a 500.

## Provider error messages are redacted for an echoed credential before storage or display
*2026-07-30*
Decision: `apollo._safe_reason` and `llm._safe_gemini_reason` now take the API key used for the request and replace any occurrence of it in the extracted provider message with `[REDACTED]` before truncating and returning it.
Why: A provider's own error message can, in principle, echo back part of the request that included the credential (e.g. an error that quotes an invalid header value). The existing sanitizers already avoided raw payloads and URLs, but hadn't accounted for a provider intentionally or accidentally echoing the key inside an otherwise-legitimate message field. Added by SDE 2 during the hardening pass and adopted as-is after review.
Rejected: Nothing rejected — this closes a real gap with no downside; the redaction only ever fires on the rare case where a key substring appears in a message, and is a no-op otherwise.

## Gemini structured output uses provider-side responseJsonSchema in addition to local Pydantic validation
*2026-07-30*
Decision: `app/llm.py` sends `generationConfig.responseJsonSchema`, derived from `schema.model_json_schema()` with a small set of unsupported keywords stripped (currently `default`, `$schema`), on every structured-output call. Local Pydantic validation and the existing two-shot corrective retry are unchanged and remain the final authority.
Why: Verified against the current official Gemini API reference (ai.google.dev/api/generate-content) before coding, per the hardening instructions — the native `generateContent` endpoint accepts a standard JSON Schema via `responseJsonSchema`, which is the least-lossy way to hand it a schema Pydantic already produces (as opposed to hand-converting to the older, more restrictive `responseSchema` OpenAPI subset). Provider-side enforcement reduces how often the model returns something that fails local validation at all, without replacing local validation as the actual guarantee.
Rejected: Relying on local validation alone (the original Slice 2 behavior) — works, but leaves more of the burden on the two-shot retry than necessary. Also rejected: switching to `responseSchema` — well-documented and stable, but a lossier target for a schema that's already a full JSON Schema.

## Gemini model updated from gemini-2.5-flash to gemini-3.6-flash
*2026-07-30*
Decision: `GEMINI_MODEL` in `app/llm.py` changed from `gemini-2.5-flash` to `gemini-3.6-flash`.
Why: Live verification of the hardening pass, run against a newly rotated Gemini key pasted through Settings, returned Gemini's own error: "This model models/gemini-2.5-flash is no longer available to new users." This is exactly the condition the hardening instructions required before touching the model — documentation review alone hadn't caught it, but the live call did. Per instructions, implementation stopped and asked the owner before changing anything; the owner confirmed the switch to `gemini-3.6-flash`, the current stable flash-tier model per ai.google.dev/gemini-api/docs/models. Re-verified live afterward: `intake.llm_ok` recorded, a correctly LLM-parsed Brief produced (cleanly split product/audience/niche, not the heuristic's raw-text truncation).
Rejected: Leaving `gemini-2.5-flash` configured. Would have shipped hardening whose live-key path was never actually provably exercised — every real key would silently degrade to the heuristic via `GEMINI_ERROR`, defeating the point of correction 8's live verification.

## New dependency: unittest-based test suite (no new package)
*2026-07-30*
Decision: `tests/test_slice2_hardening.py` uses Python's built-in `unittest` plus `unittest.mock`, both already in the standard library — no new test framework dependency added to `requirements.txt`.
Why: This is the project's first maintained, retained test module (prior verification was always a disposable script per collaboration.md rule 15). `unittest` covers everything needed here (mocked httpx responses, `fastapi.testclient.TestClient`, a temporary SQLite file) without introducing pytest or any other package, honoring CLAUDE.md's "no new dependency unless necessary."
Rejected: pytest. More ergonomic for larger suites, but an unnecessary new dependency for 32 tests when unittest already does the job.

## Fit-scoring is one batch LLM call, not a per-target loop
*2026-07-31*
Decision: `app/agent/scoring.py`'s `score_batch()` asks Gemini to score every discovered target in a single structured call (`FitBatch`, a list of per-target `FitAssessment`s keyed by `target_index`), rather than calling `generate_structured` once per target.
Why: A per-target loop over up to 25 targets, each with the existing two-shot retry, could block campaign creation for tens of minutes, and would turn a single rejected credential into a repeated 401/403 storm. One batch call bounds latency independent of target count and makes a credential failure a single call, not a loop — this was an owner-directed correction to the original per-target design during Slice 3 planning review.
Rejected: Per-target scoring with a concurrency cap and per-call timeout. Would have needed explicit early-abort logic on a credential failure and async/thread-pool machinery for no real benefit here, since a single batch call removes the hazard by construction.

## Fit citations are grounded, not just schema-valid
*2026-07-31*
Decision: `FitReason` requires `evidence_key`/`evidence_value` (plus a non-empty `reason`), and `scoring._is_grounded()` checks that pair against the target's actual normalized evidence — key present, value not `None`/blank, and value matching — before a score is ever stored. Any assessment with even one ungrounded reason is discarded, and that single target falls back to the deterministic heuristic (which is grounded by construction, since it only ever cites fields it just read).
Why: An owner review of the first plan draft pointed out that checking only "is `citation` non-empty" would let a hallucinated citation through unchallenged. A schema can enforce shape but not truth; grounding has to be checked against the real evidence at runtime.
Rejected: Trusting the schema alone (the original plan). Passed a non-empty-string test but not a "did this actually happen" test.

## Evidence is normalized at the Source.evidence() boundary, not read from raw candidate data
*2026-07-31*
Decision: Each source (`apollo.py`, `seed.py`) gained its own `normalize_evidence()` mapping to one shared shape (`name`, `industry`, `employees`, `country`, `domain`); `Source.evidence()` now returns that normalized shape, and `sources.evidence_for(source_used, candidate)` dispatches to the right normalizer without the route holding a live `Source` object.
Why: Apollo's raw payload uses `estimated_num_employees`; seed rows use `employees`. The original plan had scoring read `candidate.raw` directly, which would have made `scoring.py` know both providers' field names — exactly the per-provider coupling the source-agnostic non-negotiable exists to prevent. Fixed before implementation per owner review.
Rejected: Deferring normalization to Slice 5 (the original plan's stated simplification). Correction concluded the coupling should never have shipped even for Slice 3's two sources.

## Targets and their fit scores are persisted in one transaction, with a length guard
*2026-07-31*
Decision: `db.add_scored_targets()` replaces the create-campaign path's use of `add_targets` (kept only for the existing isolation test). It writes every target row together with its `fit_score`/`fit_reasons_json` in one `executemany`/commit, and raises `ValueError` — writing zero rows — if `len(candidates) != len(scores)`, checked before any connection is opened.
Why: Separate target-insert and fit-update steps (the original plan's shape) could leave a campaign with some targets scored and others not if the process died in between. The length guard exists so a future refactor that breaks the 1:1 alignment between candidates and scores fails loudly instead of a `zip()`-based insert silently dropping the longer list's tail.
Rejected: A `zip()`-based insert with no length check. Would silently truncate on a mismatch rather than surfacing the bug.

## Zero discovered targets is an explicit, audited no-op
*2026-07-31*
Decision: If discovery returns no candidates, `create_campaign` writes a `scoring.skipped_no_targets` audit row (no banner) and redirects immediately, without calling `score_batch` or `add_scored_targets` at all.
Why: The original plan didn't say what should happen when discovery yields nothing (e.g. a `SEED_ERROR` with an empty list) — flagged by owner review as an undefined case. An explicit branch keeps the empty-candidates path from ever reaching a batch-scoring call with nothing to score, and keeps the audit trail honest about what actually happened.
Rejected: Silently falling through to `score_batch([])` without a dedicated audit action. Works (the function does handle an empty list safely), but leaves no record of *why* no scoring audit row exists for that campaign.

## Scoring skips its own Gemini call when intake already learned the key is rejected
*2026-07-31*
Decision: `scoring.score_batch()` gained a `known_invalid_key_reason` keyword parameter; `create_campaign` passes `intake_result.reason` through it whenever `intake_result.status == IntakeStatus.INVALID_GEMINI_KEY`. When set, `score_batch` skips its own live call and heuristic-scores every target directly, reporting `INVALID_GEMINI_KEY` with the same reason intake already recorded.
Why: A route-level diagnostic found that one campaign request with an invalid Gemini key made two live Gemini HTTP calls — intake's (which correctly got the terminal 403) and a second, entirely redundant one from scoring, since the two steps had no way of telling each other what they'd already learned. A rejected credential doesn't become valid between two calls milliseconds apart in the same request.
Rejected: Leaving scoring to always call the LLM independently (the original Slice 3 design). Correct in isolation, but wasteful and slower by exactly one avoidable round-trip whenever intake had already established the key was bad.

## Apollo's normalized "name" field defaults the same way Candidate.name does
*2026-07-31*
Decision: `apollo.normalize_evidence()`'s `name` field is now `raw.get("name") or "Unknown company"`, mirroring the exact default `_to_candidate` already applies to `Candidate.name`. `_heuristic()`'s zero-evidence fallback branch was also changed to cite `evidence.get("name")` directly — if that's falsy too, it now returns zero reasons rather than fabricating a citation.
Why: A malformed/empty Apollo organization object (a real, if rare, live-API shape) produced `Candidate.name == "Unknown company"` (via its own default) while `candidate.raw` — and therefore the *evidence* dict — had no `"name"` key at all. The heuristic's old fallback branch then invented the literal string `"this target"` as a citation, which didn't match the evidence's real (missing) name value — an ungrounded citation manufactured by the exact code that exists to prevent ungrounded citations.
Rejected: Leaving the heuristic's `or "this target"` placeholder in place. It satisfied "always emit a reason" but not "the reason must be true," which is the actual requirement.

## Industry-overlap scoring stems words before comparing, and its explanation names only what it evaluated
*2026-07-31*
Decision: `_heuristic()`'s industry-overlap component now compares `_stemmed_tokens()` (a minimal, longest-suffix-first strip — not a real stemmer) rather than raw tokens, so "distributors," "distributor," "distribution," and "distribute" count as the same term. The no-overlap explanation text was also changed from "doesn't match the brief's niche or product" to "doesn't match the brief's niche."
Why: A natural demo brief phrased as "US distributors for magnesium" scored obvious wholesale/health distributors as a poor industry fit, purely because "distributors" and "distribution" are different inflections of the same word and exact-token matching doesn't see the relationship. Separately, the explanation claimed to evaluate `brief.product`, which this component never reads — misleading regardless of the score.
Rejected: A full stemming library (e.g. Porter). This project runs on no new dependencies without necessity (CLAUDE.md), and a handful of common English suffixes is enough to close the specific, demonstrated gap without new project complexity. Verified the fix doesn't change any of the seven canonical-brief anchor scores already pinned in the retained test suite, since that brief's niche text already matched those industries verbatim before stemming.

## Evidence employee counts are coerced to int at the normalization boundary, and the heuristic guards defensively too
*2026-07-31*
Decision: `app/sources/base.py` gained `coerce_int()`, used by both `apollo.normalize_evidence()` and `seed.normalize_evidence()` to turn a numeric-looking string (or float) into an int, or `None` if it can't be read as one. `_heuristic()` also independently guards its own `employees` handling (treating a non-int, or a `bool`, as unavailable) before doing any arithmetic comparison.
Why: A route-level diagnostic found that an evidence dict with `employees: "180"` (a string) raised `TypeError` on `100 <= employees <= 600`, contradicting `score_batch`'s own "never raises" contract. Fixing only the two current sources' normalization would have made the crash unreachable in practice, but not made the contract actually true — `_heuristic()` takes a plain dict, not a validated schema, so it is a real boundary in its own right and guards accordingly.
Rejected: Fixing only at the source-normalization boundary and trusting `_heuristic()` to receive well-typed evidence forever. Works today, but leaves the module's own documented guarantee false for any future caller or source that doesn't happen to go through `coerce_int()` first.
