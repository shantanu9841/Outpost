# Outpost — Product Decision Record 2.0

This is the reader-facing version of Outpost's working decision log. The decisions and corrections came from the build; the wording here was consolidated afterward from `DECISIONS.md`, `SPEC.md`, `PROGRESS.md`, slice plans, review findings, and the implementation itself. It does not pretend every paragraph was written at the exact moment of the decision.

The purpose of the record is to show how the product changed as constraints and implementation evidence became clearer: what triggered each choice, what was deliberately left out, and what would make the choice worth revisiting.

## Operating principles

- Solve one real founder workflow before claiming a broad market.
- Prefer user trust and truthful system status over impressive-looking automation.
- Spend engineering effort where it improves or tests the core product loop.
- Treat provider cost, failure, and provenance as product behavior—not backend trivia.
- Keep the product evaluable without paid credentials.
- Use AI for implementation speed while keeping scope and release decisions explicit.

---

## 1. Build one coherent product, not a checklist of AI demos

**Phase:** Before implementation  
**Status:** Active

**Trigger**  
The starting inspiration was a list of twelve agentic-AI portfolio projects: structured output, grounded retrieval, memory, human approval, cost routing, evaluation, observability, multi-agent debate, and more.

**Decision**  
Build one product that uses the relevant capabilities inside a real workflow rather than twelve disconnected demos. Outpost combines structured output, evidence grounding, persistent context, human approval, cost-aware routing, and automated draft evaluation.

**Why**  
The hiring signal I wanted was not “I completed a list.” It was the ability to decide which capabilities belong in a product, integrate them coherently, and reject attractive work that does not improve the user loop.

**Trade-off accepted**  
I did not build observability infrastructure, event-triggered automation, multi-agent debate, or a portfolio-dependent open-source contribution. Those could be legitimate engineering projects, but they would have delayed a complete user workflow.

**Revisit when**  
Real usage exposes reliability or operational problems that require those capabilities.

---

## 2. Build an outreach workbench, not a marketing site

**Phase:** Problem framing  
**Status:** Active  
**Evidence available:** One real founder workflow; broader demand unvalidated

**Trigger**  
A friend launching a consumer brand needed to find supply-chain partners, niche operators, and creators, then reach out without adding a large marketing or business-development stack.

**Decision**  
Build a workflow product that carries business context from campaign intake through discovery, fit assessment, drafting, approval, and relationship tracking.

**Why**  
The recurring work was not publishing a page. It was identifying who mattered, deciding whether they fit, learning enough to be specific, and drafting outreach without starting from zero for every target.

**Trade-off accepted**  
This is a product hypothesis from a narrow starting point. Outpost is not evidence that a broad segment wants the product, will adopt it repeatedly, or will get better outreach outcomes.

**Revisit when**  
Five to eight founder-led brands have attempted real campaigns and repeated-use behavior can be compared.

---

## 3. Keep the private use case, but make the public product category-safe

**Phase:** Public positioning  
**Status:** Active

**Trigger**  
The original request came from a founder in a regulated adult consumer category. The portfolio version needed to be public, while promotion in that category is restricted across major platforms and creates an avoidable mismatch with my previous health-tech work.

**Decision**  
Use functional-wellness CPG as the public demo context. It preserves the same operating problem—creator awareness plus physical distribution—without turning Outpost into a nicotine-marketing product. A private instance can use different seed data and business context.

**Why**  
The product mechanics remain honest while the public artifact is safer to demonstrate and more coherent with the rest of my work.

**Trade-off accepted**  
The public demo is an analogous workflow, not a literal representation of the initiating brand.

**Revisit when**  
The product is tested with several categories and can be demonstrated using a real consenting customer case.

---

## 4. Use one engine for creator and business outreach

**Phase:** Product architecture  
**Status:** Active

**Trigger**  
The initiating use case required both creator promotion and business relationships such as distribution and logistics.

**Decision**  
Use one campaign, evidence, scoring, drafting, approval, audit, and pipeline engine across two target types: `creator` and `business`. Only source-specific discovery and evidence normalization vary.

**Why**  
After discovery, both flows ask the same questions: Is this target relevant? What evidence supports that? What should we say? Is the message good enough to approve? What happened next?

**Rejected**  
Separate influencer-outreach and B2B-outreach products.

**Trade-off accepted**  
Some target-specific nuance is compressed into a common model. The abstraction remains useful only while the downstream workflows are genuinely shared.

**Revisit when**  
One target type requires materially different approvals, compliance, message structure, or pipeline states.

---

## 5. Use licensed providers and keep discovery replaceable

**Phase:** Discovery design  
**Status:** Active

**Trigger**  
LinkedIn and social scrapers offered attractive coverage, but introduced terms-of-service risk, brittle demos, account exposure, and a weak dependency to defend publicly.

**Decision**  
Use Apollo for businesses, YouTube for creators, and Apify for Instagram and TikTok. Put every live provider and the seed source behind one `Source` contract that returns normalized candidates and evidence.

**Why**  
The product should inherit provider coverage—not provider structure. A replaceable boundary keeps scoring, drafting, approvals, and the pipeline stable when a source changes.

**Rejected**  
LinkedIn scraping, self-hosted social scrapers, and provider-specific data handling inside the core workflow.

**Trade-off accepted**  
Outpost inherits provider pricing, quotas, coverage limits, and API changes.

**Revisit when**  
A compliant provider no longer meets minimum coverage or reliability and a replacement can satisfy the same normalized contract.

---

## 6. The agent drafts; a human decides

**Phase:** Core trust boundary  
**Status:** Active

**Trigger**  
Personalized outreach can be wrong, off-brand, or inappropriate even when the model output is well-formed. Auto-send would turn a draft error into an external action.

**Decision**  
Require a person to edit, approve, or reject every draft. Outpost tracks workflow state but has no message-transmission path.

**Why**  
The approval queue is not a temporary missing feature. It preserves brand control, catches weak personalization, and lowers the trust required to try the product. It also avoids pretending that maximum throughput is the same thing as effective outreach.

**Rejected**  
Auto-send, auto-post, and implying that moving a target to `contacted` means Outpost transmitted a message.

**Trade-off accepted**  
The user still performs the final send, so Outpost cannot claim end-to-end outreach automation.

**Revisit when**  
Real usage establishes edit and approval patterns, and a controlled integration can preserve review, rate limits, consent, and auditability.

---

## 7. Make users bring their own keys—and preserve a zero-key path

**Phase:** Cost and evaluation model  
**Status:** Active

**Trigger**  
The prototype needed to remain usable without creating an open-ended provider bill. Requiring several paid integrations before the workflow could be evaluated would also increase setup friction.

**Decision**  
Store YouTube, Apify, Apollo, and Gemini credentials per workspace. Use the workspace owner's key for live calls, with no environment fallback. Preserve the full workflow through seeded targets and deterministic heuristics when keys are absent.

**Why**  
Variable cost follows the person generating it. The prototype can be handed off without making me its permanent operator, and a recruiter or user can experience the complete loop before paying for providers.

**Rejected**  
A shared server-owned key, hidden environment fallback, and a setup flow that blocks until every integration is configured.

**Trade-off accepted**  
BYO keys add friction and locally stored credentials are not production secret management. This is appropriate for a local single-owner prototype, not a hosted multi-customer product.

**Revisit when**  
Hosted usage and retention justify managed billing, authentication, and production credential storage.

---

## 8. Turn provider failure into honest product behavior

**Phase:** Live provider verification  
**Status:** Active  
**Trigger:** A real Apollo free-tier key returned `403` on every discovery endpoint

**What changed**  
The first implementation treated provider failure as a crash and risked giving the wrong remediation. Live testing showed that a valid credential can still lack plan access—a normal condition in a BYO-key product.

**Decision**  
Model no key, invalid key, insufficient plan, rate limit, network failure, provider failure, and seed failure as distinct states. Every source reports the provider attempted, the source actually used, a typed status, and a sanitized reason. Fallback data remains available, but is never presented as live.

**Why**  
“Check your key” is false when the credential is valid but the plan lacks access. Silent seed fallback is worse: the workflow appears successful while the provenance is wrong.

**Outcome**  
Provider failure became part of the source contract and interface rather than hidden exception handling. Audit rows preserve what happened without exposing credentials.

---

## 9. Require evidence grounding, not just valid JSON

**Phase:** Scoring and drafting review  
**Status:** Active  
**Trigger:** Plan review showed that schema-valid model output could still cite invented facts

**Decision**  
Normalize provider evidence before scoring. Require every fit reason to cite an exact evidence key/value pair and validate it against the source data before persistence. Drafts may use only verified evidence, and the cited value must appear in the message.

**Why**  
Structured output guarantees shape, not truth. Personalization has value only when it is grounded in something actually known about the target.

**Rejected**  
Trusting a non-empty citation, checking only that the target name appears, or accepting output because it passes a schema.

**Trade-off accepted**  
When grounding fails, Outpost returns a plainer deterministic result instead of showing a more fluent but unsupported one.

**Revisit when**  
The evidence model becomes too restrictive for useful personalization and a broader grounding rule can be tested without weakening traceability.

---

## 10. Bound model calls before adding orchestration

**Phase:** Campaign efficiency  
**Status:** Active

**Trigger**  
One model call per target would make latency and cost grow linearly, and an invalid credential could trigger the same failed request repeatedly across a campaign.

**Decision**  
Score the discovered batch in one structured call, validate results per target, and fall back per target when needed. If intake has already established that the Gemini credential is invalid, skip the redundant scoring request. For creator campaigns, choose one provider deterministically: Apify when configured, otherwise YouTube, otherwise seed data.

**Why**  
This reduces round-trips, bounds failure amplification, and keeps source provenance and cost explainable without introducing asynchronous job infrastructure.

**Rejected**  
Per-target concurrent calls and automatic aggregation across every available creator source.

**Trade-off accepted**  
A single batch is less granular to retry, and one creator source may provide less coverage than aggregation. Per-target validation and partial fallback preserve correctness.

**Revisit when**  
Measured latency, batch size, or cross-source coverage becomes a user problem and justifies deduplication or background processing.

---

## 11. Evaluate quality and gate every stronger-model dollar

**Phase:** Quality and routing  
**Status:** Implemented; paid escalation dormant

**Trigger**  
Using the strongest model for every target would spend money where expected value is low. Token count alone also does not tell a user whether a draft is usable.

**Decision**  
Evaluate each draft across personalization, specificity, non-genericness, and clarity of ask. Start with the default model or heuristic. Escalate only when the workspace has its own key, paid routing is explicitly enabled, fit is at least 85, the first draft scores below 80, and the stronger model has verified finite, positive pricing.

**Why**  
The clearest case for incremental spend is a high-fit target with a weak first draft. Cost and quality should be visible in the same decision.

**Rejected**  
Always using the strongest model, calling a provider tier “free,” or enabling a model before its pricing can be calculated honestly.

**Trade-off accepted**  
The stronger-model path is implemented and tested but remains off. An honest dormant capability is preferable to an unverified paid demo.

---

## 12. Protect spend before persistence

**Phase:** Concurrency review  
**Status:** Active  
**Trigger:** Review found that simultaneous draft requests could both spend before database uniqueness rejected one result

**What changed**  
A unique active-draft constraint protected stored state, but it ran after the irreversible external call. It prevented duplicate records—not duplicate cost.

**Decision**  
Acquire a short-lived, workspace-scoped generation reservation before any model request, release it afterward, and keep the final uniqueness constraint as a second layer.

**Why**  
The cost guard has to sit before the spend. Holding a database transaction open across a network request would solve one problem by creating another, so the reservation uses a crash-backstop expiry instead.

**Outcome**  
Double-submit races are blocked before provider usage, while final database state remains protected independently.

---

## 13. Optimize the stack for iteration and inspection

**Phase:** Delivery design  
**Status:** Active

**Trigger**  
The primary risk was whether the workflow was useful, not whether the service could scale horizontally. A separate frontend application, container stack, and cloud deployment would expand implementation surface without testing the core hypothesis.

**Decision**  
Use Python, FastAPI, SQLite, server-rendered HTML, a token-based light/dark design system, and minimal vanilla JavaScript. Build in vertical slices and retain regression tests after every slice.

**Why**  
The stack is easy to run, inspect, and change during AI-assisted solo development. A design contract written before templates also prevented visual drift across sessions.

**Rejected**  
A frontend framework, Docker as a prerequisite, cloud infrastructure, and production authentication before real usage.

**Trade-off accepted**  
The architecture is optimized for a local prototype, not a multi-user production service.

**Revisit when**  
Collaboration, deployment, latency, or concurrency becomes a measured user constraint.

---

## 14. Make the repository the memory and separate implementation from review

**Phase:** AI-assisted operating model  
**Status:** Active

**Trigger**  
Long AI sessions lose context, fresh sessions reinterpret vague requirements, and a model reviewing its own implementation often defends the choices it just made.

**Decision**  
Keep scope, design, decisions, and verified progress in versioned repository files. Require a written plan before each slice and use a different coding agent for independent review.

**Why**  
The repository gives every session a stable product contract. Independent review introduces different failure patterns instead of repeating the implementing model's blind spots.

**Evidence from the build**

- A full environment switch recovered from repository context without losing the next step or product boundary.
- One slice began before plan approval and produced thirteen uncommitted changes. I preserved them on a branch, reset to the last verified commit, replanned, and then reviewed each file for reuse, adaptation, or rejection.
- Review caught an identical-request “retry,” a misleading generic `llm` setting name, overstated multi-tenancy language, the duplicate-spend race, and invalid pricing that accepted `NaN`.

**Trade-off accepted**  
Plans, review gates, and context files add overhead. The payoff is visible history, recoverability, and fewer silently accumulated assumptions.

---

## 15. Describe the prototype precisely and keep validation debt visible

**Phase:** Current boundary  
**Status:** Active

**Trigger**  
Implementation review showed that “multi-tenant” overstated what workspace scoping guarantees. The repository also proves build quality, not market demand.

**Decision**  
Describe Outpost as a local, single-owner prototype with explicit workspace data scoping. Do not claim security-grade multi-tenancy, automated sending, production credential management, or validated product-market fit. Treat the next phase as workflow validation rather than feature expansion.

**Why**  
There are no user accounts or authorization checks, and the active workspace is controlled by a client cookie. Likewise, 292 passing tests demonstrate retained implementation behavior—not that users want the product or that outreach improves.

**Next evidence to collect**

1. Time from campaign brief to first approved draft.
2. Approval, edit, and rejection rates by target type and source.
3. Repeated use for a second campaign.
4. Manually sent reply rate by fit band.
5. Qualitative reasons users reject a target or rewrite a draft.

**Revisit major scope choices when**  
This evidence identifies the dominant bottleneck. Until then, accounts, shared-team permissions, CRM integration, automated sending, payments, and broad source aggregation remain intentionally deferred.

---

## Current guardrails

| Area | Current rule |
|---|---|
| User control | Nothing sends automatically; every draft is reviewed. |
| Truthfulness | No model score or draft persists without evidence grounding. |
| Cost | Provider usage is BYO-key; paid escalation requires opt-in and verified pricing. |
| Fallbacks | The interface preserves the real provider state and never presents fallback data as live. |
| Data scope | Every workspace-facing database operation requires an explicit `workspace_id`. |
| Prototype boundary | Workspaces separate local data, but accounts and production secret management are out of scope. |
| Delivery | Changes ship in gated slices with retained regression tests and independent review. |
| Validation | Technical completeness is not used as a substitute for user or market evidence. |

## Assumptions corrected by evidence

| Earlier assumption | Evidence and correction |
|---|---|
| A provider failure could be handled as a generic key problem | Live Apollo behavior required distinct invalid-key, plan, rate-limit, provider, network, and seed states. |
| Structured output made scores trustworthy | Runtime grounding against normalized evidence was added before persistence. |
| A unique draft row prevented duplicate model cost | A pre-call generation reservation was added after concurrency review. |
| Any configured stronger model could be used for escalation | Escalation now requires explicit opt-in and verified finite, positive pricing. |
| Route-level tests covered unedited approvals | Browser verification exposed textarea line-ending normalization that direct form tests did not reproduce. |
| Workspace-scoped queries justified “multi-tenant” | Language was narrowed to local workspace isolation because accounts and authorization do not exist. |

These corrections are the point of the record: the decisions changed when implementation evidence contradicted the earlier model of the product.
