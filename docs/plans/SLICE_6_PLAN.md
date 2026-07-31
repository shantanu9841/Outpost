# Slice 6 Plan — Evaluation and cost-aware routing

**Status:** Planning only (draft for owner review). No application code, tests,
templates, or schema change is part of this document. Implementation does not
begin until the owner approves this plan, confirms no changes remain
outstanding, and confirms the model switch (`CLAUDE.md`).

**Model:** Planned on **Opus 4.8** (routing/eval architecture is real judgment).
Execution recommendation is **Sonnet** (mechanical implementation from an
approved plan); confirm the switch at the top of implementation.

**Baseline:** branch `codex/sde-1-slice-2-hardening` at `b640b49` (the
committed post-fix Slice 5 state), clean tree, **212 passing tests**
(`python -m unittest discover -s tests`). This plan must be re-confirmed
against that state before coding.

---

## 1. Owner-approved decisions (authoritative)

1. **Model tiers — stronger Gemini tier, strict BYO-key billing.** The default
   path is the existing zero-cost heuristic (no key) or `gemini-3.6-flash`
   (free tier, key present). Escalation to a **stronger paid Gemini model**
   happens **only** when *all* hold: (a) the workspace has its own `gemini`
   key, (b) the workspace has **explicitly opted into** the stronger paid
   tier, and (c) the target is high-fit. Outpost never provides or pays for a
   key; any provider charges belong to that workspace owner's Google project.
2. **No silent escalation.** With no key, or a key but no paid-tier opt-in, the
   app stays fully functional on the zero-cost heuristic/free-model path and
   must never escalate.
3. **Eval — LLM-as-judge with a deterministic heuristic fallback.** An LLM
   judge scores the rubric when a Gemini key is present; a deterministic
   rubric scorer runs when not — the same four-status pattern as
   intake/scoring/drafting.
4. **Cost — tokens (exact) plus an estimated dollar figure.** Store exact
   token counts as the source of truth; display tokens plus an estimated `$`
   from a documented, adjustable pricing constant, clearly labelled an
   estimate.
5. **Deferred stronger model + pricing.** The exact stronger model id and its
   pricing are **deferred** until current official availability is verified.
   No paid live verification without the owner's explicit authorization;
   otherwise mocked retained tests only. Escalation is fully implemented and
   mocked-tested but cannot fire until the owner sets a verified
   `ESCALATION_MODEL` **and** opts a workspace in.
6. **Scope control — one slice, verified and committed before Slice 7 (none).**
   Slice 6 is the last slice in `SPEC.md` §6.

---

## 2. Scope

**In scope**

- `app/agent/eval.py` — rubric scoring (LLM judge + heuristic fallback), one
  `eval` row per draft, stored at draft-creation time.
- `app/agent/routing.py` — the tier decision, high-fit gate, confidence
  early-exit, escalation orchestration, and per-draft cost accounting.
- `app/llm.py` — expose Gemini `usageMetadata` token counts, and accept a
  `model` parameter so routing can call flash vs the stronger tier.
- `app/db.py` — new `eval` table (SPEC §3, idempotent); populate the existing
  `draft.cost_tokens`; a per-workspace paid-tier opt-in; draft creation now
  writes the draft + eval + cost + audit atomically.
- `app/models.py` — `EvalRubric` / `EvalResult` schemas.
- `app/audit_banners.py` — eval and routing audit actions/labels (namespaced,
  explicit maps, no enum-string interpolation).
- `app/main.py` + templates — eval score, model used, and cost per outreach on
  Approvals (and lighter on Pipeline / campaign detail); a running
  cost-per-outreach figure; a Settings checkbox for the paid-tier opt-in.

**Out of scope (unchanged)**

- Re-evaluating a human-edited draft body (eval scores the agent's created
  draft, once — SPEC §4.8). Noted as a limitation.
- Any auto-send/auto-post. Nothing outbound. Escalation never sends anything;
  it only changes which model drafts.
- A second LLM provider. Only Gemini models are used.

---

## 3. Non-negotiables honored

- **BYO-key.** The stronger tier uses the workspace's own `gemini` key and is
  billed to the workspace owner's Google project. Outpost supplies no key and
  pays for nothing (decision 1/2).
- **Demo mode.** Zero keys → heuristic drafting + heuristic eval + zero cost;
  every step completes.
- **Structured output.** The LLM judge returns a Pydantic-validated
  `EvalResult` with one retry (reusing `llm.py`).
- **Human approval.** Drafting/approval separation is unchanged; eval and
  routing only affect how the *agent* drafts and how the draft is scored.
- **Tenant isolation.** Every `eval`/`cost`/opt-in read and write is scoped by
  `workspace_id`.
- **Atomic audit.** Draft creation now commits the draft, its eval row, its
  cost, and the `draft.created` + `eval.scored` (+ `routing.escalated` when
  applicable) audit rows in one transaction, or none.

---

## 4. Model and pricing contracts (deferred where owner-gated)

- **Default model:** `gemini-3.6-flash` (already the only verified model;
  `DECISIONS.md` "Current Gemini model").
- **Stronger model (`ESCALATION_MODEL`):** a single named constant in
  `routing.py`, **unset by default**. Until the owner verifies current
  official availability and sets it, escalation cannot fire even for a
  high-fit, opted-in workspace: routing records a `routing.escalation_unavailable`
  audit note and keeps the default draft. This satisfies "defer the exact
  stronger model ID... until current official availability is verified" and
  "no paid live verification without explicit authorization" (decision 5).
- **Pricing constants:** a documented, adjustable per-model rate table
  (`PRICING`, e.g. blended `$ / 1K tokens` per model) in `routing.py`, marked
  **time-sensitive and provider-controlled** (same discipline as Slice 5's
  Apify pricing). Only used to render an estimated `$`; never a hard number
  presented as exact. Flash's current published rate is documented with a
  "re-verify before relying" note; the stronger model's rate is deferred with
  the model id.
- **Token source:** Gemini `generateContent` returns
  `usageMetadata.{promptTokenCount, candidatesTokenCount, totalTokenCount}`.
  `llm.py` reads `totalTokenCount` (falling back to prompt+candidate, then to
  `0` if absent — never raises). Confirmed shape from the official API; the
  exact field presence is defensively handled.

---

## 5. Architecture

### 5.1 `llm.py` — measured calls, selectable model (minimal blast radius)

The existing `generate_structured(schema, system, user, settings) ->
BaseModel | None` is **kept unchanged** (Slices 2–5 tests call it and mock
`llm.httpx.post`; changing its return type would break retained tests). Refactor
internally:

- `GEMINI_MODEL` stays the flash default; `GEMINI_URL` becomes a function of
  the model: `_url(model)`.
- A new `@dataclass LLMResult(value: BaseModel | None, tokens: int, model: str)`.
- A new `generate_structured_measured(schema, system, user, settings, *,
  model=GEMINI_MODEL) -> LLMResult` carries the parsing/retry logic and also
  returns token usage and the model used.
- `generate_structured(...)` becomes a thin wrapper returning
  `generate_structured_measured(...).value`, so **no existing caller or test
  changes**. Only drafting/eval/routing use the measured form.
- `_call_gemini` returns `(text, tokens)`; a missing/misshaped `usageMetadata`
  yields `tokens=0`, never a raise (same "never leak a raw exception"
  contract). Token counts are non-sensitive; they may appear in audit detail.

### 5.2 `eval.py` — rubric scoring (LLM judge + heuristic fallback)

- Schemas (`models.py`): `EvalRubric` (four integer fields, each **0–25**:
  `personalization`, `specificity`, `non_genericness`, `clear_ask`) and
  `EvalResult` (the rubric plus a derived `score` 0–100 = the sum, plus a
  short per-dimension `justification`). Validated; out-of-range rejected.
- `EvalStatus` mirrors the established four-way split: `LLM_OK`,
  `NO_GEMINI_KEY`, `INVALID_GEMINI_KEY`, `GEMINI_ERROR`, plus
  `HEURISTIC_FALLBACK` (LLM replied but failed validation twice).
- `evaluate_draft(brief, target, draft_body, settings, *,
  known_invalid_key_reason=None) -> EvalOutcome(result, status, tokens,
  model_used, reason)`. Uses `generate_structured_measured`; on no key /
  rejected key / error / unparseable-twice, falls back to the deterministic
  heuristic. Reuses `known_invalid_key_reason` to skip a call the same request
  already proved rejected.
- **LLM judge** scores the final draft body against the brief and the target's
  stored, grounded Slice 3 evidence. Structured, so no free-form number.
- **Heuristic judge** (deterministic, demo-grade — documented as a proxy, not
  a quality model): `personalization` from whether the body names the
  recipient identity; `specificity` from whether the body contains the draft's
  grounded cited evidence value; `non_genericness` from the **absence** of the
  drafting module's own banned filler phrases (reuse that list) plus basic
  sentence-length variety; `clear_ask` from the presence of a single
  question/ask. Each 0–25; grounded by construction (it only inspects the real
  body).

### 5.3 `routing.py` — tier decision, high-fit gate, early-exit, cost

`route_and_draft(brief, target, settings) -> RoutingOutcome` orchestrates the
existing `drafting.draft_outreach` and `eval.evaluate_draft`, and is called by
`create_draft` in place of the direct `draft_outreach` call:

1. **Default draft.** `drafting.draft_outreach(brief, target, settings)` —
   heuristic if no key, flash if key present (unchanged behavior). Eval it.
2. **Escalation eligibility (all required):** `settings.get("gemini")` present
   **and** workspace paid-tier opt-in enabled **and**
   `target.fit_score >= HIGH_FIT_THRESHOLD` (**85**, reusing design.md's
   "success" fit band) **and** `ESCALATION_MODEL` is configured/verified.
3. **Confidence early-exit.** If eligible **but** the default draft's eval
   `score >= CONFIDENCE_THRESHOLD` (**80**, named/adjustable) → keep the
   default draft (SPEC "early-exit when confident"). Audit `routing.early_exit`.
4. **Escalate.** If eligible and not confident → re-draft with
   `ESCALATION_MODEL` (`draft_outreach(..., model=ESCALATION_MODEL)` — drafting
   gains an optional `model` param threaded to `generate_structured_measured`),
   re-eval the escalated body, keep the escalated draft. Audit
   `routing.escalated`.
5. **Opted-in but model unavailable.** Eligibility (a)+(b)+(c) met but
   `ESCALATION_MODEL` unset → **no escalation**, keep default, audit
   `routing.escalation_unavailable` (never silent — decision 2/5).
6. **Cost.** `cost_tokens` = sum of tokens across every LLM call actually made
   for this outreach (default draft + default eval, plus escalated draft +
   escalated eval when escalated); heuristic calls contribute `0`.
   `model_used` = the model that produced the **stored** body
   (`"heuristic"` / `"gemini-3.6-flash"` / the stronger id).

`RoutingOutcome` carries the final body, `model_used`, `cost_tokens`, the final
`EvalResult`/`EvalStatus`, and the routing decision (for the audit). All
thresholds and the model/pricing constants live as named module constants,
easy for the owner to adjust.

### 5.4 Paid-tier opt-in storage

Stored as a per-workspace **non-secret** setting, `paid_tier`, in the existing
`workspace_setting` table (value `"1"` when enabled) — reuses `get_settings` /
`save_setting` plumbing with **no migration**. It is deliberately **not** added
to `db.SETTING_KEYS` (which drives the masked-key UI loop), so it never renders
as a masked credential. Settings gains a dedicated checkbox for it, saved via a
small explicit handler, and `routing.py` reads `settings.get("paid_tier") ==
"1"`. *(Alternative considered: a dedicated `workspace.paid_tier_enabled`
column via idempotent `ALTER TABLE`. Rejected for now as heavier than reusing
the existing per-workspace store for one boolean; flagged here so the owner can
choose the column instead if preferred.)*

### 5.5 `db.py` — eval table, cost, atomic draft creation

- **`eval` table** (SPEC §3, `CREATE TABLE IF NOT EXISTS`, idempotent):
  `id, workspace_id, draft_id, rubric_json, score, created_at`. Every read
  scoped by `workspace_id`. (`eval` is not a SQLite keyword; used as-is.)
- **`cost_tokens`** on `draft` is populated at creation (was reserved-NULL).
- **Atomic creation.** `add_draft` is extended (or a new
  `add_draft_with_eval`) so the draft row, its `cost_tokens`, the `eval` row,
  and the `draft.created` + `eval.scored` (+ routing) audit rows commit in one
  transaction — honoring the atomic-audit non-negotiable. The existing
  one-active-draft-per-target unique-index guard and `ActiveDraftExists`/
  `NotFound` behavior are preserved.
- Read helpers: `get_eval_for_draft`, and a workspace-scoped
  `outreach_cost_summary(workspace_id)` returning total tokens, est. cost, and
  draft count for the running cost-per-outreach figure.

### 5.6 `main.py` + templates

- `create_draft` calls `routing.route_and_draft`, then the atomic
  draft+eval+cost creation. Its existing redirects/guards are unchanged.
- **Approvals** (`approvals.html`): each draft card shows model used, an eval
  score badge (with the four-dimension rubric on expand, same caret pattern as
  fit reasons), and cost (`N tokens · ~$X.XXXX est.`). A header strip shows the
  running **cost per outreach** (avg cost across the workspace's drafts).
- **Pipeline** / **campaign detail**: lighter — eval score + cost shown per
  card/row where a draft exists; no new controls.
- **Settings** (`settings.html`): a checkbox "Enable the stronger paid model
  tier for high-fit outreach — uses *your* Gemini key; your Google project is
  billed," with copy making the BYO-billing explicit. Disabled/greyed with a
  hint when no `gemini` key is saved (can't escalate without a key).
- Reuse existing design tokens only; no new colors/spacing. Eval score can
  reuse a coloring band analogous to `_fit_class` (its own thresholds).

---

## 6. Verification and acceptance criteria

Proportional to risk (collaboration.md rule 9). Baseline: the post-Slice-5
retained suite still passes, plus new `tests/test_slice6_eval_routing.py`
(mocked at the `llm`/`httpx` boundary — no live call, no real key, temp SQLite).

Acceptance criteria, each with at least one retained test:

1. **Cost recorded.** A flash-drafted outreach stores `cost_tokens` from mocked
   `usageMetadata`; a heuristic (no-key) outreach stores `0`. A missing
   `usageMetadata` yields `0`, never a raise.
2. **Eval stored per draft.** Every created draft gets exactly one `eval` row
   (LLM path and heuristic path), scoped to its workspace, with a 0–100 score
   and the four-dimension rubric.
3. **Eval LLM-judge + fallback.** LLM judge result is used when valid; no key /
   rejected key / error / twice-invalid all fall back to the heuristic with the
   correct `EvalStatus`; a rejected key already known in the request is not
   re-tried.
4. **No silent escalation — no key.** No `gemini` key → heuristic path, `0`
   cost, never escalates, regardless of fit or opt-in.
5. **No silent escalation — no opt-in.** `gemini` key present but `paid_tier`
   not enabled → flash default only, never escalates, even for a fit-100
   target.
6. **High-fit gate.** Key + opt-in + `ESCALATION_MODEL` set: a target below
   `HIGH_FIT_THRESHOLD` is **not** escalated; a target at/above it **is**
   (mocked stronger-model call), and the escalated body/model/cost are stored.
7. **Confidence early-exit.** Key + opt-in + high-fit but the default draft's
   eval `>= CONFIDENCE_THRESHOLD` → no escalation; `routing.early_exit` audited;
   only the default call's tokens are billed.
8. **Escalation unavailable.** Key + opt-in + high-fit but `ESCALATION_MODEL`
   unset → no escalation, `routing.escalation_unavailable` audited, default
   draft kept (never silent).
9. **Cost sums across calls.** An escalated outreach's `cost_tokens` equals the
   sum of default-draft + default-eval + escalated-draft + escalated-eval mocked
   token counts; `model_used` is the stronger id.
10. **Atomic creation.** If eval or cost writing fails, no draft/eval/audit row
    is left behind (transaction rolls back); the one-active-draft guard and
    `NotFound`/`ActiveDraftExists` behavior are intact.
11. **Running cost-per-outreach.** `outreach_cost_summary` returns the correct
    average across a workspace's drafts and is workspace-scoped (another
    workspace's drafts never leak in).
12. **Tenant isolation.** `eval` rows, `cost`, and the `paid_tier` opt-in never
    cross workspaces.
13. **Backward compatibility.** All existing Slice 2–5 tests pass unchanged
    (the `generate_structured` wrapper preserves the old signature); an existing
    business/creator draft still drafts and approves exactly as before when no
    paid tier is involved.
14. **Estimated-$ rendering.** The cost estimate is computed from the
    documented rate table and clearly labelled an estimate; tokens are shown as
    the exact source of truth. (Unit test on the formatter; UI computed-style
    check for light/dark.)
15. **Sanitized audit/cost details.** No key ever appears in an eval/routing
    audit detail or cost string; a rejected-key reason is sanitized as in prior
    slices.

**Safe live verification (deletable, only if authorized).** No paid live
verification without the owner's explicit authorization (decision 5). If the
owner authorizes it, a temporary DB-write-free script may make **one** bounded
flash call to confirm the real `usageMetadata` shape (free tier, no paid
model), then be deleted (rule 11). The stronger-model path is verified by
mocked tests only unless/until the owner both sets `ESCALATION_MODEL` and
authorizes a bounded paid check.

**UI.** Computed-style light/dark checks for the new eval/cost elements; ≤2
final screenshots.

---

## 7. Files touched by the implementation (for reference — not this document)

New: `app/agent/eval.py`, `app/agent/routing.py`,
`tests/test_slice6_eval_routing.py`.
Modified: `app/llm.py`, `app/models.py`, `app/db.py`, `app/audit_banners.py`,
`app/main.py`, `app/templates/approvals.html`,
`app/templates/pipeline.html`, `app/templates/campaign_detail.html`,
`app/templates/settings.html`, `PROGRESS.md`, `DECISIONS.md`,
`docs/history/COLLABORATION_LOG.md`, `collaboration.md`. No `requirements.txt`
change. No schema change beyond the new `eval` table (and the reused
`workspace_setting` opt-in; a `paid_tier` column only if the owner prefers the
alternative in §5.4).

**This planning commit** would touch only `docs/plans/SLICE_6_PLAN.md`,
`collaboration.md`, and `docs/history/COLLABORATION_LOG.md` — and only once
SDE 2's Slice 5 fixes are committed and the tree is clean.

---

## 8. Remaining assumptions / owner decisions to confirm at review

- **Stronger model id + pricing** are deferred until official availability is
  verified; escalation stays inert until the owner sets `ESCALATION_MODEL` and
  opts a workspace in (decision 5).
- **Opt-in storage** (§5.4): reuse `workspace_setting` (recommended, no
  migration) vs a dedicated `workspace.paid_tier_enabled` column.
- **Thresholds:** `HIGH_FIT_THRESHOLD = 85`, `CONFIDENCE_THRESHOLD = 80` —
  proposed defaults, adjustable.
- **Eval score scale:** four dimensions × 0–25 = 0–100. Confirm the shape.
- **Cost `$` under escalation** is a labelled estimate using `model_used`'s
  rate (exact for the common single-model case; a small approximation when two
  models contributed). Confirm this is acceptable vs. adding a stored
  exact-cost column.
