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
