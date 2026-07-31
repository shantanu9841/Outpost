# Slice 6 Plan — Evaluation and cost-aware routing

**Status:** Planning only (draft for owner review). This is **v2**, correcting
ten SDE 2 review findings against v1 (`2f991a5`) — see §0. No application
code, tests, templates, or schema change is part of this document.
Implementation does not begin until the owner approves this plan, confirms no
changes remain outstanding, and confirms the model switch (`CLAUDE.md`).

**Model:** Planned on **Opus 4.8** (routing/eval architecture is real
judgment). Execution recommendation is **Sonnet** (mechanical implementation
from an approved plan); confirm the switch at the top of implementation.

**Baseline:** branch `codex/sde-1-slice-2-hardening` at `b640b49` (the
committed post-fix Slice 5 state), clean tree, **212 passing tests**
(`python -m unittest discover -s tests`). This plan must be re-confirmed
against that state before coding.

---

## 0. v2 correction summary

SDE 2 reviewed v1 (`2f991a5`) and the owner approved ten corrections, applied
below. Each is cross-referenced to where it lands in this document:

1. **Strictly workspace-key-only.** §4.1 removes the `GEMINI_API_KEY`
   environment fallback from `app/llm.py` — a change to already-shipped
   Slice 2 code, not only new Slice 6 modules — so every LLM workflow
   (intake, scoring, drafting, eval, routing) is workspace-key-only. New
   acceptance criteria (§6, items 1–2) require an env key to be provably
   inert.
2. **Per-attempt usage records.** §4.2 replaces the single-token `LLMResult`
   with `TokenUsage` (model, prompt/input, candidates/output, thinking,
   total — each independently nullable).
3. **Accumulate usage across every attempt.** §4.2/§4.3 make
   `generate_structured_with_usage` and `LLMError` both carry a
   `list[TokenUsage]` covering the first attempt, the retry, and any attempt
   that ultimately falls back to a heuristic — sanitized, never a raw
   payload or credential.
4. **No silent zero.** §4.4 makes "no model call was made" (`0`, known) and
   "a model call happened but usage is unreadable" (`None`, unknown) two
   distinct, never-conflated states, propagated through the aggregate.
5. **Correct dollar accounting.** §4.4/§5.5 replace the blended-rate idea
   with a per-attempt, per-token-type breakdown priced at *that attempt's own
   model's* rates, persisted once at creation time as `cost_breakdown_json` +
   integer `estimated_cost_microusd` so historical estimates never drift when
   pricing constants change later.
6. **Terminal invalid-key behavior.** §5.3 step 2 makes a rejected key
   discovered during default drafting terminal for the whole routing
   request — eval and escalation make no further Gemini calls. New
   call-count test (§6, item 9).
7. **Exactly one eval per draft.** §5.6's `eval` table declares
   `draft_id INTEGER NOT NULL UNIQUE REFERENCES draft(id)`, workspace-scoped,
   written atomically with the draft/cost/audit rows.
8. **Complete heuristic rubric.** §4.5 fully specifies all four 0–25
   dimensions (exact point tables, boundary behavior, normalization,
   `BANNED_FILLER_PHRASES` shared constant, sentence-variety and
   question-counting algorithms, missing-data behavior) and the exact
   nested Pydantic shape for per-dimension justifications.
9. **Corrected billing language.** §3, §5.7, and settings copy replace "free
   model"/"free tier" wording with "default model" and "estimated paid
   list-price cost"; state plainly that default drafting and the LLM judge
   spend the workspace owner's own quota once a key is present. Genuinely
   zero-cost only ever means "no workspace key at all."
10. **Completion semantics.** §1 decision 6 and §8 state explicitly that
    Slice 6 cannot be marked complete against `SPEC.md` until the exact
    stronger model is owner-approved and passes the required verification
    gate — disabled, mocked-tested escalation plumbing is an acceptable
    interim state, never a paid live call without explicit authorization.

Also resolved per the owner's instruction: **paid-tier opt-in storage** is now
a firm decision — a dedicated, idempotently migrated `workspace` boolean
column (§5.6), not the `workspace_setting`-reuse alternative v1 left open.

---

## 1. Owner-approved decisions (authoritative)

1. **Model tiers — stronger Gemini tier, strict BYO-key billing.** The
   default path is the existing zero-cost heuristic (no key) or the
   **default model** `gemini-3.6-flash` (key present — see decision 9 on
   language). Escalation to a **stronger paid Gemini model** happens
   **only** when *all* hold: (a) the workspace has its own `gemini` key,
   (b) the workspace has **explicitly opted in** via the dedicated
   `paid_tier_enabled` column (§5.6), (c) the target is high-fit
   (`fit_score >= HIGH_FIT_THRESHOLD`), and (d) no rejected-key terminal
   condition applies to this request (decision 6 / §5.3 step 2). Outpost
   never provides or pays for a key; any provider charges belong to that
   workspace owner's Google project.
2. **No silent escalation.** With no key, or a key but no paid-tier opt-in,
   the app stays on the zero-cost heuristic / default-model path and must
   never escalate.
3. **Eval — LLM-as-judge with a deterministic heuristic fallback.** An LLM
   judge scores the rubric when a Gemini key is present and not already
   known-rejected this request; a fully-specified deterministic rubric
   scorer (§4.5) runs otherwise — the same status-carrying pattern as
   intake/scoring/drafting.
4. **Cost — exact per-attempt tokens, never blended; estimated paid
   list-price dollars.** Persist a per-attempt, per-token-type breakdown
   (§4.4/§4.5); the aggregate `draft.cost_tokens` and
   `draft.estimated_cost_microusd` are `NULL` (unknown) whenever any
   contributing attempt's usage is unreadable, and `0` (known) only when no
   model call was made at all. Historical estimates are computed once at
   creation time and never recomputed from later pricing constants.
5. **Deferred stronger model + pricing.** The exact stronger model id and
   its pricing are **deferred** until current official availability is
   verified. No paid live verification without the owner's explicit
   authorization; otherwise mocked retained tests only. Escalation is fully
   implemented and mocked-tested but cannot fire until the owner sets a
   verified `ESCALATION_MODEL` **and** opts a workspace in.
6. **Slice 6 completion is gated, separate from Slice 6 being merged.**
   Slice 6's code, tests, and UI may be complete, committed, and correct
   while `ESCALATION_MODEL` stays unset. But Slice 6 is **not** marked
   complete against `SPEC.md` §6 ("high-fit targets route to the better
   model only when a key exists") until the owner approves a specific
   stronger model id and that model passes the same kind of safe
   verification gate Slice 5 used (§6 of this document, "Safe live
   verification"). This is a documentation/completion-tracking rule, not
   a code gate — the code gate is `ESCALATION_MODEL is None`.

---

## 2. Scope

**In scope**

- `app/agent/eval.py` (new) — rubric scoring (LLM judge + fully-specified
  heuristic fallback, §4.5), one `eval` row per draft, stored at
  draft-creation time.
- `app/agent/routing.py` (new) — the tier decision, high-fit gate, terminal
  invalid-key short-circuit, confidence early-exit, escalation
  orchestration, and per-outreach cost accounting/pricing.
- `app/agent/drafting.py` (modified) — exposes `BANNED_FILLER_PHRASES` as a
  real, importable constant (previously only prose inside `SYSTEM_PROMPT`);
  `DraftResult` gains a `usage: list[TokenUsage]` field; `draft_outreach`
  gains an optional `model` parameter so routing can call the escalation
  tier through the same function. No behavior change to the existing
  business/creator drafting logic itself.
- `app/llm.py` (modified) — **removes the `GEMINI_API_KEY` environment
  fallback** (correction 1 — affects every existing caller, not only Slice
  6); adds `TokenUsage`, `generate_structured_with_usage`, and a
  model-selectable request; `generate_structured` becomes a thin
  backward-compatible wrapper.
- `app/db.py` (modified) — new `eval` table (draft-unique, workspace-scoped,
  idempotent); idempotent `ALTER TABLE` additions for
  `workspace.paid_tier_enabled`, `draft.cost_breakdown_json`,
  `draft.estimated_cost_microusd`; a new atomic
  `create_draft_with_routing(...)` that writes the draft, its cost columns,
  its eval row, and every required audit row in one transaction (the
  existing `add_draft` is untouched, still used where it already is).
- `app/models.py` (modified) — `EvalDimension`, `EvalRubric`, `EvalResult`
  schemas (§4.5).
- `app/audit_banners.py` (modified) — eval and routing audit
  actions/labels (namespaced, explicit maps, no enum-string interpolation).
- `app/main.py` + templates (modified) — eval score, model used, and
  per-outreach cost on Approvals (lighter on Pipeline / campaign detail); a
  running cost-per-outreach figure; a Settings checkbox for the paid-tier
  opt-in; a corrected Gemini Settings hint (the current copy references the
  environment-variable fallback this plan removes).

**Out of scope (unchanged)**

- Re-evaluating a human-edited draft body (eval scores the agent's created
  draft, once — SPEC §4.8). Noted as a limitation.
- Any auto-send/auto-post. Nothing outbound. Escalation never sends
  anything; it only changes which model drafts.
- A second LLM provider. Only Gemini models are used.
- Gemini's own transport (`app/llm.py` still sends the API key as a `key=`
  query parameter, per the code as shipped in Slice 2–5). Correcting that to
  header auth, the way Slice 5 corrected Apify/YouTube, is a real
  improvement but was not one of the ten corrections in this review pass;
  flagged here so it isn't mistaken for an oversight, not undertaken now.

---

## 3. Non-negotiables honored

- **BYO-key.** The default model and the stronger tier both use the
  workspace's own `gemini` key exclusively (decision 1 of the correction
  summary) and are billed to the workspace owner's Google project. Outpost
  supplies no key and pays for nothing.
- **Demo mode.** Zero keys → heuristic drafting + heuristic eval + `0` known
  cost; every step completes. This is the **only** genuinely zero-cost path
  (correction 9) — a key present, even for the default model, means real
  usage against that key's quota.
- **Structured output.** The LLM judge returns a Pydantic-validated
  `EvalResult` with one retry (reusing `llm.py`).
- **Human approval.** Drafting/approval separation is unchanged; eval and
  routing only affect how the *agent* drafts and how the draft is scored.
- **Tenant isolation.** Every `eval`/cost/opt-in read and write is scoped by
  `workspace_id`.
- **Atomic audit.** `create_draft_with_routing` commits the draft (with its
  cost columns), its eval row, and every required audit row
  (`draft.created`, `eval.scored`, plus a routing-decision action) in one
  transaction, or none.

---

## 4. Core mechanics (usage, cost, pricing, rubric)

### 4.1 `app/llm.py` — workspace-key-only, no environment fallback

**Correction 1.** `_resolve_key` changes from
`settings.get("gemini") or os.environ.get("GEMINI_API_KEY")` to strictly
`settings.get("gemini")`. This is a change to code shipped in Slice 2, used
by every existing LLM call site (`intake.py`, `scoring.py`, `drafting.py`)
as well as the new `eval.py`/`routing.py` — "every product LLM workflow" per
the correction, not only new Slice 6 code. The module docstring's "Key
resolution" paragraph is corrected to match (no more mention of
`GEMINI_API_KEY`). `os` becomes an unused import in `llm.py` and is removed.

No other Slice 2–5 behavior changes: a workspace with its own key still
works exactly as before; a workspace with no key still gets `None` from
`generate_structured` and falls back to a heuristic, exactly as today —
only the *environment* variable stops being consulted anywhere.

### 4.2 `TokenUsage` — one record per attempt, no field silently zeroed

```python
@dataclass
class TokenUsage:
    model: str
    prompt_tokens: int | None       # usageMetadata.promptTokenCount
    candidates_tokens: int | None   # usageMetadata.candidatesTokenCount
    thinking_tokens: int | None     # usageMetadata.thoughtsTokenCount
    total_tokens: int | None        # usageMetadata.totalTokenCount
```

**Correction 2.** Replaces v1's single `LLMResult(value, tokens, model)`.
One `TokenUsage` is produced per HTTP 200 response actually received from
Gemini — not per logical call, so a two-shot retry produces up to two
records (correction 3).

**Population rule (correction 4 — no silent zero):**

- If the response has no `usageMetadata` object at all, or it is not a JSON
  object: **all four fields are `None`** (fully unknown) for that attempt.
  This is a malformed/incomplete provider response, not a legitimate zero.
- If `usageMetadata` is present as an object: `prompt_tokens`,
  `candidates_tokens`, and `total_tokens` each read their documented key
  only when it is present and an `int`; otherwise `None` (unknown) — these
  three fields are always expected on a real response, so their absence
  signals an incomplete payload, not a true zero.
- `thinking_tokens` is the one exception: `thoughtsTokenCount` is
  legitimately absent from `usageMetadata` for a model call that used no
  extended thinking (a normal, documented case, not malformed). When
  `usageMetadata` is present but has no `thoughtsTokenCount` key,
  `thinking_tokens = 0` (known zero — thinking genuinely did not happen),
  distinct from the whole-block-missing case above where it is `None`.
- A response received but a `RequestError`/non-2xx status: **no
  `TokenUsage` record is created for that attempt at all** — no response
  body was ever obtained, so there is nothing to report as either zero or
  unknown; the attempt simply contributes nothing to the usage list.

### 4.3 Accumulation through retries and failures (correction 3)

`generate_structured_with_usage(schema, system, user, settings, *,
model=GEMINI_MODEL) -> MeasuredResult`:

```python
@dataclass
class MeasuredResult:
    value: BaseModel | None    # None only when no workspace key is configured
    usage: list[TokenUsage]    # 0, 1, or 2 entries
```

- No key configured → `MeasuredResult(None, [])`. (Zero calls, zero usage
  entries — the "no model call was made" case from correction 4.)
- First attempt gets a non-2xx/transport failure → raises `LLMError` with
  `usage=[]` (nothing was ever billable-and-observed).
- First attempt succeeds (200) and validates → `MeasuredResult(parsed,
  [usage1])`.
- First attempt succeeds (200) but fails validation → retry is issued.
  - Retry fails transport/status → raises `LLMError` with `usage=[usage1]`
    (the first, wasted attempt's usage is preserved even though the overall
    call failed).
  - Retry succeeds (200) and validates → `MeasuredResult(parsed, [usage1,
    usage2])`.
  - Retry succeeds (200) but fails validation twice → raises `LLMError(kind=
    ERROR, message="model output failed validation twice", usage=[usage1,
    usage2])`.

`LLMError` gains a `usage: list[TokenUsage]` attribute (default `[]`),
populated exactly as above. `TokenUsage` only ever holds a model name and
plain integers/`None` — attaching it to `LLMError` cannot leak a provider
payload, header, URL, or credential, the same guarantee `LLMError.message`
already upholds via `_safe_gemini_reason`.

**Backward compatibility (unchanged from v1's intent, restated precisely):**
`generate_structured(schema, system, user, settings) -> BaseModel | None`
keeps its exact current signature and return type — it becomes
`return generate_structured_with_usage(schema, system, user, settings).value`.
Every Slice 2–5 caller and test that calls `generate_structured` or catches
`LLMError` and reads `.kind`/`.message` is unaffected; they simply never
look at the new `.usage` attribute. `LLMError.usage` defaulting to `[]`
means even an untouched call site behaves identically if it never reads
the new field.

### 4.4 Cost aggregation, "unknown" vs. "zero", and dollar accounting

**Correction 4 (no silent zero) + correction 5 (no blended rate, no
mixed-model mispricing) + correction 9 (no false "free"):**

A single outreach (one `create_draft` call) can accumulate `TokenUsage`
records from up to four sources: the default draft's model call(s), the
default draft's eval call(s), an escalated draft's model call(s) (only if
escalation actually happened), and the escalated draft's eval call(s).
`routing.py` collects every one of these into one flat
`cost_breakdown: list[TokenUsage]` for the outreach (§5.3).

- **No calls made at all** (fully heuristic: no key, or a key but
  heuristic-only fallback with zero successful HTTP 200s anywhere) →
  `cost_breakdown = []`, `cost_tokens = 0`, `estimated_cost_microusd = 0`.
  Known-zero, never ambiguous with "unknown."
- **At least one call made, and every contributing `TokenUsage.total_tokens`
  is a known int** → `cost_tokens = sum(total_tokens)`,
  `estimated_cost_microusd` computed as below.
- **At least one call made, but any contributing `TokenUsage.total_tokens`
  is `None`** → `cost_tokens = NULL` and `estimated_cost_microusd = NULL`
  for the draft row (the aggregate cannot honestly claim a specific number).
  `cost_breakdown_json` still preserves every attempt's actual known/unknown
  fields individually — the detail view can show "default draft: 512
  tokens (gemini-3.6-flash); eval: usage unknown" even though the top-line
  total is "unknown," never a fabricated blended figure.

**Dollar estimate (correction 5):** computed once, at creation time, as
`sum over cost_breakdown of (that attempt's own model's per-token-type
rate × that attempt's own prompt/output/thinking token counts)` — never
`total_tokens × the final/escalated model's rate`, and never a single
blended `$/token` figure across models. Any single unknown field within an
otherwise-priceable attempt makes the whole estimate `NULL` (same rule as
`cost_tokens`, so the two are never inconsistent with each other).

```python
# app/agent/routing.py — time-sensitive, provider-controlled; re-verify
# against the official Gemini API pricing page before relying on a figure
# (same discipline as Slice 5's Apify/YouTube pricing — SLICE_5_PLAN.md §4.3).
PRICING_USD_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "gemini-3.6-flash": {"input": <verify>, "output": <verify>, "thinking": <verify>},
    # ESCALATION_MODEL's entry is added once the owner approves that model
    # id and its official pricing is verified (decision 5/6).
}
```

The exact numeric rates are **not fabricated in this plan** — they are
placeholders to be filled from the live, official Gemini pricing page
immediately before implementation (not part of this correction pass, and
not a "paid live call": reading a public pricing page is not a billed API
request). Implementation must not proceed with a guessed number.

`estimated_cost_microusd` is an integer count of millionths of a US dollar
(matching the correction's preferred unit) so the stored figure never drifts
from floating-point rounding and a later change to
`PRICING_USD_PER_MILLION_TOKENS` can never retroactively alter a
historical draft's stored estimate — only future drafts see a new rate.

**Billing language (correction 9):** "default model" replaces "free model"/
"free tier" everywhere in this plan and in the UI copy it specifies (§5.7).
Default drafting and the LLM judge both consume the workspace owner's own
Gemini quota and **may incur real charges** the moment a `gemini` key is
present, regardless of whether escalation ever fires. The UI always labels
the dollar figure "estimated paid list-price cost," never implying it is
free or discounted. The only workspace state that is genuinely zero-cost is
no `gemini` key at all (fully heuristic drafting and fully heuristic eval).

### 4.5 The complete deterministic heuristic rubric (correction 8)

Reused constant, moved from prose into code — **`BANNED_FILLER_PHRASES`**,
defined in `app/agent/drafting.py` (the module that already describes these
phrases to the LLM in `SYSTEM_PROMPT`) and imported by `eval.py`, so the
prompt's prose and the heuristic's check can never silently drift apart
without a diff showing both:

```python
BANNED_FILLER_PHRASES = (
    "i love what you're doing",
    "huge fan",
    "reaching out",
    "excited to connect",
    "explore synergies",
    "at its core",
    "in today's landscape",
)
```
(All lower-case; checks are case-insensitive substring matches against the
normalized body.)

**Shared helpers reused, not reimplemented:** `eval.py` imports
`drafting._recipient_identity`, `drafting._norm_for_substring`, and
`app.agent.drafting.BANNED_FILLER_PHRASES` rather than duplicating any of
this logic — the same discipline `scoring.py`/`drafting.py` already use for
`app.sources.base.canonical_name`/`coerce_int`.

**`EvalDimension` — the exact Pydantic shape for a justification (correction
8's last requirement):**

```python
class EvalDimension(BaseModel):
    points: int
    justification: str

    @field_validator("points")
    @classmethod
    def in_range(cls, v: int) -> int:
        if not 0 <= v <= 25:
            raise ValueError("points must be between 0 and 25")
        return v

    @field_validator("justification")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("justification is required")
        return v

class EvalRubric(BaseModel):
    personalization: EvalDimension
    specificity: EvalDimension
    non_genericness: EvalDimension
    clear_ask: EvalDimension

class EvalResult(BaseModel):
    rubric: EvalRubric
    score: int  # 0-100

    @model_validator(mode="after")
    def score_matches_sum(self) -> "EvalResult":
        total = (
            self.rubric.personalization.points + self.rubric.specificity.points
            + self.rubric.non_genericness.points + self.rubric.clear_ask.points
        )
        if self.score != total:
            raise ValueError("score must equal the sum of the four dimensions' points")
        return self
```

The LLM judge is asked (via `generate_structured_with_usage(EvalResult,
...)`) to return this exact nested shape — schema-enforced provider-side
plus local Pydantic validation, matching the two-layer discipline `llm.py`
already applies. The heuristic below builds the identical shape, so
`EvalResult` reads identically regardless of which path produced it.

**Sentence splitting (shared primitive for dimensions 3 and 4):**
`_sentences(body: str) -> list[str]`: split on
`re.split(r'(?<=[.!?])\s+', body.strip())`, drop empty/whitespace-only
results. Word count of a sentence: `len(sentence.split())`.

**Dimension 1 — `personalization` (0–25):**

- `identity = drafting._recipient_identity(target)`.
- `identity is None` → **0 points**. Justification: `"No identifiable
  recipient name or handle was available to personalize with."`
- `identity` is not `None` and `drafting._norm_for_substring(identity)` is a
  substring of `drafting._norm_for_substring(body)` → **25 points**.
  Justification: `f"The message addresses {identity} directly."`
- `identity` is not `None` but not found in the body → **0 points**.
  Justification: `f"{identity} was available but is never named in the
  message."`

**Dimension 2 — `specificity` (0–25):** grounded against the target's
*stored* Slice 3 evidence (`drafting._parse_fit_reasons(target)`), not
re-derived from the draft's own claimed citation — this checks whether the
message contains *a* real, specific, verifiable fact about the target, the
general quality signal "specificity" is about, independent of exactly which
one fact the drafting step happened to pick.

- `reasons = drafting._parse_fit_reasons(target)`; if empty → **0 points**
  (defensive only — unreachable in practice, since `assert_grounded`
  guarantees ≥1 stored reason post-Slice-3). Justification: `"No stored
  evidence was available to check for a specific detail."`
- If any `reasons[i]["evidence_value"]`, normalized via
  `drafting._norm_for_substring`, is a substring of the normalized body →
  **25 points**. Justification: `f"The message cites a specific, verified
  detail ({reasons[i]['evidence_value']!r})."`
- Otherwise → **0 points**. Justification: `"The message contains no
  specific, verifiable detail about the target."`

**Dimension 3 — `non_genericness` (0–25):** two independent sub-checks,
summed (four possible totals: `0`, `10`, `15`, `25`):

- *Banned-phrase check (0 or 15):* if none of `BANNED_FILLER_PHRASES`
  appear (case-insensitive substring) in the body → **15**; if any appear →
  **0**.
- *Sentence-variety check (0 or 10):* let `lengths = [word count of s for s
  in _sentences(body) if s.split()]`. If `len(lengths) >= 2` and
  `len(set(lengths)) > 1` (at least two sentences, not all the same length)
  → **10**; otherwise (fewer than two sentences, or all sentences the same
  length) → **0**.
- `points = banned_phrase_points + variety_points`. Justification names
  which sub-checks passed/failed, e.g. `"No filler phrases found; sentence
  lengths vary."` / `"Contains a filler phrase ('reaching out'); sentence
  lengths do not vary."` (the exact matched phrase is named when one is
  found, since it is drawn from the constant list, never from provider
  output — safe to surface).

**Dimension 4 — `clear_ask` (0–25):** `question_count = sum(1 for s in
_sentences(body) if s.rstrip().endswith("?"))`.

- `question_count == 1` → **25 points**. Justification: `"The message makes
  exactly one clear ask."`
- `question_count == 0` → **0 points**. Justification: `"The message makes
  no discernible ask."`
- `question_count >= 2` → **10 points**. Justification: `f"The message
  makes {question_count} asks instead of one focused ask."`

**Missing-data behavior:** if `draft_body` is blank/empty (defensive only —
unreachable given `validate_draft_body`'s 20–1500 character floor), every
dimension scores `0` with justification `"The draft body was unavailable to
evaluate."`; `score = 0`.

**`evaluate_draft` signature:**

```python
def evaluate_draft(
    brief: Brief, target: dict, draft_body: str, settings: dict[str, str], *,
    known_invalid_key_reason: str | None = None,
) -> EvalOutcome: ...

@dataclass
class EvalOutcome:
    result: EvalResult
    status: EvalStatus       # LLM_OK | NO_GEMINI_KEY | INVALID_GEMINI_KEY | GEMINI_ERROR
    usage: list[TokenUsage]  # every attempt made by this call, per §4.3
    model_used: str          # GEMINI_MODEL, the escalation model, or "heuristic"
    reason: str | None       # sanitized, safe for UI/audit
```

`EvalStatus` intentionally mirrors the same four-way split
`IntakeStatus`/`ScoreStatus` already use (`LLM_OK`, `NO_GEMINI_KEY`,
`INVALID_GEMINI_KEY`, `GEMINI_ERROR`) rather than v1's extra
`HEURISTIC_FALLBACK` value — "the LLM replied but failed validation twice"
already resolves to `GEMINI_ERROR` via the existing `LLMErrorKind.ERROR`
mapping, so a fifth status would be redundant with the established pattern.

---

## 5. Architecture

### 5.1 `llm.py` — measured calls, selectable model, no env fallback

Combines §4.1 and §4.2/§4.3: `GEMINI_MODEL` stays the default-model
constant; `_url(model)` replaces the hardcoded `GEMINI_URL`.
`_call_gemini(api_key, system, user, response_schema, model)` returns
`(text, TokenUsage)` on a 200 response (never raises for a parseable-or-not
JSON body — only for transport/status failures, per the existing contract),
using the population rule in §4.2. `generate_structured_with_usage` performs
the two-shot retry loop from §4.3. `generate_structured` is the thin
backward-compatible wrapper from §4.3.

### 5.2 `eval.py` — rubric scoring (LLM judge + fully-specified heuristic)

`evaluate_draft` (§4.5's signature): if `known_invalid_key_reason` is set,
skip the live call entirely and return the heuristic result with
`status=INVALID_GEMINI_KEY` and `usage=[]` (mirrors `scoring.score_batch`'s
existing `known_invalid_key_reason` short-circuit). Otherwise call
`llm.generate_structured_with_usage(EvalResult, SYSTEM_PROMPT_EVAL,
_build_eval_prompt(brief, target, draft_body), settings)`; on
`LLMError` (whether `INVALID_KEY` or `ERROR`), fall back to the heuristic
but **keep the error's `usage`** (§4.3) so tokens spent on a failed judge
attempt are never silently dropped from the outreach's cost. On success,
use the LLM's `EvalResult` and its usage. On no key (`value is None`), fall
back to the heuristic with `usage=[]`.

The LLM judge prompt includes the brief, the target's normalized evidence,
and the drafted body; it is asked to score using the same four dimensions
and point ranges as the heuristic (0–25 each), so the two paths are
philosophically aligned even though the LLM path can use real judgment
where the heuristic uses fixed rules.

### 5.3 `routing.py` — tier decision, terminal invalid-key, early-exit, cost

```python
HIGH_FIT_THRESHOLD = 85       # inclusive
CONFIDENCE_THRESHOLD = 80     # inclusive
ESCALATION_MODEL: str | None = None  # unset until owner-verified (decision 5/6)
```

`route_and_draft(brief, target, settings) -> RoutingOutcome`, called by
`create_draft` in place of the direct `draft_outreach` call:

1. **Default draft.** `drafting.draft_outreach(brief, target, settings)` —
   heuristic if no key, default model if key present. Collect its `usage`.
2. **Terminal invalid-key check (correction 6).** If the default draft's
   `status == DraftStatus.INVALID_GEMINI_KEY`, this key is now known-rejected
   for the remainder of the request:
   - Eval is called with `known_invalid_key_reason` set (§5.2) — **no**
     live judge call.
   - Escalation eligibility is forced to `False` regardless of opt-in/fit —
     **no** escalation call, regardless of how high the target's fit score
     is. Audit `routing.invalid_key_terminal`.
   - Skip directly to step 6 (cost).
3. **Eval the default draft.** `eval.evaluate_draft(brief, target,
   default_body, settings)` (no `known_invalid_key_reason` here, since step
   2 didn't trigger). Collect its `usage`.
4. **Escalation eligibility (all required, only reached if step 2 did not
   trigger):** `settings.get("gemini")` present **and**
   `db.get_paid_tier_enabled(workspace_id)` **and**
   `target["fit_score"] >= HIGH_FIT_THRESHOLD` **and** `ESCALATION_MODEL is
   not None`.
   - Not eligible for any reason except a set-but-inapplicable
     `ESCALATION_MODEL` → keep the default draft/eval, audit nothing extra
     (this is the ordinary, non-escalating path, same as most Slice 4
     drafts today).
   - Eligible on (gemini key + opt-in + fit) but `ESCALATION_MODEL is None`
     → keep default, audit `routing.escalation_unavailable` (never
     silent — decision 2 of §0/§1).
5. **Confidence early-exit / escalate.** If eligible and `ESCALATION_MODEL`
   is set:
   - Default eval's `score >= CONFIDENCE_THRESHOLD` → keep the default
     draft, audit `routing.early_exit`.
   - Else → `drafting.draft_outreach(brief, target, settings,
     model=ESCALATION_MODEL)`, collect its usage, `eval.evaluate_draft(...)`
     the escalated body, collect that usage, keep the escalated
     body/eval/model. Audit `routing.escalated`.
6. **Cost.** `cost_breakdown` = the concatenation of every `usage` list
   collected above, in the order collected. `cost_tokens` /
   `estimated_cost_microusd` computed per §4.4. `model_used` = the model
   that produced the **stored** body (`"heuristic"` /
   `"gemini-3.6-flash"` / the escalation id).

```python
@dataclass
class RoutingOutcome:
    body: str
    model_used: str
    eval_result: EvalResult
    eval_status: EvalStatus
    cost_breakdown: list[TokenUsage]
    cost_tokens: int | None            # None means unknown, 0 means no calls made
    estimated_cost_microusd: int | None
    routing_action: str  # "default" | "early_exit" | "escalated"
                          # | "escalation_unavailable" | "invalid_key_terminal"
```

All thresholds, `ESCALATION_MODEL`, and `PRICING_USD_PER_MILLION_TOKENS`
are named module constants, easy for the owner to adjust.

### 5.4 `drafting.py` changes (widened scope, correction 2/3/8)

- `BANNED_FILLER_PHRASES` constant added (§4.5); `SYSTEM_PROMPT`'s existing
  prose is left as-is (it already names the same phrases in English for the
  LLM) with a comment tying the two together so they cannot silently drift.
- `DraftResult` gains `usage: list[TokenUsage] = field(default_factory=
  list)` as a fifth, defaulted field — every construction site inside
  `drafting.py` is updated to pass the real accumulated usage (`[]` for the
  heuristic path, the `MeasuredResult`/`LLMError` usage for the model
  path); any test that only calls `draft_outreach(...)` and reads
  attributes off the returned `DraftResult` is unaffected by the added
  field.
- `draft_outreach(brief, target, settings, *, known_invalid_key_reason=None,
  model=GEMINI_MODEL)` gains the optional `model` parameter, threaded to
  `generate_structured_with_usage`, so routing's escalation call (§5.3 step
  5) reuses the exact same function instead of duplicating drafting logic
  for a second model.

### 5.5 Cost/pricing computation helper

A pure function in `routing.py`:
`_price(cost_breakdown: list[TokenUsage]) -> tuple[int | None, int | None]`
returning `(cost_tokens, estimated_cost_microusd)` per the rules in §4.4 —
unit-testable independent of any HTTP mocking, which is how the "mixed-model
pricing" and "unknown usage" acceptance criteria (§6) are verified precisely.

### 5.6 `db.py` — eval table, paid-tier column, cost columns, atomic creation

**Paid-tier opt-in (resolved, no longer open — owner's instruction):** a
dedicated, idempotently migrated boolean column on `workspace`:

```sql
ALTER TABLE workspace ADD COLUMN paid_tier_enabled INTEGER NOT NULL DEFAULT 0
```

guarded by a small `_add_column_if_missing(conn, table, column, ddl)`
helper (SQLite has no `ADD COLUMN IF NOT EXISTS`; existence is checked via
`PRAGMA table_info(table)` before executing the `ALTER TABLE`, so `init()`
stays safe to call on every startup). The same helper adds `draft`'s two new
columns:

```sql
ALTER TABLE draft ADD COLUMN cost_breakdown_json TEXT
ALTER TABLE draft ADD COLUMN estimated_cost_microusd INTEGER
```

Default `0` on `workspace.paid_tier_enabled` makes every **existing**
workspace (Alpha, Beta, the various `*Verify` workspaces from Slices 1–5)
opted **out** automatically — no behavior change for any workspace that
doesn't explicitly opt in, and product configuration (not a credential)
correctly lives as a real column rather than piggybacking on
`workspace_setting`. New functions: `get_paid_tier_enabled(workspace_id) ->
bool`, `set_paid_tier_enabled(workspace_id, enabled: bool) -> None`.

**`eval` table (correction 7 — exactly one per draft, SPEC §3, idempotent):**

```sql
CREATE TABLE IF NOT EXISTS eval (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
    draft_id      INTEGER NOT NULL UNIQUE REFERENCES draft(id),
    rubric_json   TEXT    NOT NULL,
    score         INTEGER NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
)
```

`draft_id ... UNIQUE` is both the foreign key and the "exactly one eval per
draft" guarantee at the database level — a second attempt to insert an eval
for the same `draft_id` raises `sqlite3.IntegrityError`, identified the same
way `_is_active_draft_conflict` already identifies the Slice 4 unique-index
violation. `workspace_id` stays an explicit column (not join-only), per the
existing "every tenant function takes `workspace_id`" discipline —
retained even though `draft_id` alone is already unique.

**Atomic creation.** A new function, **not** a change to the existing
`add_draft` (kept exactly as-is for its current callers/tests):

```python
def create_draft_with_routing(
    workspace_id: int, target_id: int, outcome: RoutingOutcome, actor: str = "agent",
) -> int:
    """Insert the draft (with its cost columns), its eval row, and every
    required audit row in one transaction. Raises NotFound / ActiveDraftExists
    exactly as add_draft does; raises a distinct EvalAlreadyExists (identified
    the same way _is_active_draft_conflict is) if the eval UNIQUE constraint
    is ever hit, which should be unreachable given one eval is written per
    newly-inserted draft in the same transaction."""
```

On any failure partway through (the draft insert's own tenancy check, the
eval insert, or an audit insert), the whole transaction rolls back — no
draft, no eval, no cost, no audit row is left behind. The existing
one-active-draft-per-target unique index and its `ActiveDraftExists`
behavior are preserved unchanged (this function still performs the same
`INSERT ... SELECT ... WHERE target.workspace_id = ?` tenancy-enforcing
insert as `add_draft`, just also carrying the cost columns and eval row).

**Read helpers:** `get_eval_for_draft(workspace_id, draft_id)`, and a
workspace-scoped `outreach_cost_summary(workspace_id)` returning total known
tokens, total known estimated cost, count of drafts with unknown cost, and
draft count — for the running cost-per-outreach figure (§5.7). Unknown-cost
drafts are excluded from the average and reported as a separate count, never
silently treated as `0` (correction 4 applied to the summary too).

### 5.7 `main.py` + templates

- `create_draft` calls `routing.route_and_draft`, then
  `db.create_draft_with_routing`. Its existing redirects/guards are
  unchanged.
- **Approvals** (`approvals.html`): each draft card shows model used, an
  eval score badge (four-dimension rubric with justifications on expand,
  same caret pattern as fit reasons), and cost — `"N tokens · ~$X.XXXX
  estimated paid list-price cost"` when known, `"cost unknown"` when not,
  `"0 tokens (heuristic, no cost)"` when no key was ever used. A header
  strip shows the running cost-per-outreach average (excluding
  unknown-cost drafts, with a visible count of how many are excluded).
- **Pipeline** / **campaign detail:** lighter — eval score + cost shown per
  card/row where a draft exists; no new controls.
- **Settings** (`settings.html`): (a) a checkbox "Enable the stronger paid
  model tier for high-fit outreach — uses *your* Gemini key; your Google
  project is billed for both the default and stronger tiers," disabled/
  greyed with a hint when no `gemini` key is saved; (b) the existing Gemini
  key-card hint is corrected — it currently reads "Uses GEMINI_API_KEY when
  configured; otherwise Outpost uses its built-in demo heuristic," which
  describes the environment fallback this plan removes (correction 1). New
  copy: "Required for the default and stronger-tier model calls; without a
  key, Outpost uses its built-in demo heuristic at zero cost." No "free"
  language anywhere in the new or corrected copy (correction 9) — a UI-copy
  acceptance test (§6) asserts the word does not appear in any eval/cost/
  paid-tier template string.
- Reuse existing design tokens only; no new colors/spacing. Eval score can
  reuse a coloring band analogous to `_fit_class` (its own thresholds).

---

## 6. Verification and acceptance criteria

Proportional to risk (collaboration.md rule 9). Baseline: the Slice 5
retained suite (212 tests) still passes, plus new
`tests/test_slice6_eval_routing.py` (mocked at the `llm`/`httpx` boundary —
no live call, no real key, temp SQLite).

1. **Environment key cannot trigger drafting.** With `GEMINI_API_KEY` set in
   `os.environ` and no workspace `gemini` key, a draft is produced by the
   heuristic path (`model_used == "heuristic"`, `cost_tokens == 0`) — the
   env var is provably inert.
2. **Environment key cannot trigger eval or escalation.** Same environment
   setup: `eval.evaluate_draft` returns `EvalStatus.NO_GEMINI_KEY`, and
   routing never escalates even with `paid_tier_enabled=True` and a
   high-fit target, because escalation also requires a *workspace* key.
3. **Usage accumulates across the retry.** A mocked first-attempt-invalid,
   second-attempt-valid sequence produces `MeasuredResult.usage` with two
   entries, both attached; a `LLMError` raised after two failed validations
   carries both entries via `.usage`.
4. **Failure-path usage is not dropped.** When the default draft's Gemini
   call fails validation twice (falls back to the heuristic body), the
   outreach's `cost_breakdown` still includes both wasted attempts' known
   token counts, and `cost_tokens` reflects them — not `0`.
5. **Known-zero vs. unknown are never conflated.** (a) A fully heuristic
   outreach (no key) → `cost_tokens == 0`, `cost_breakdown_json == "[]"`. (b)
   A real model call with a well-formed `usageMetadata` → `cost_tokens`
   equals the mocked total. (c) A 200 response with `usageMetadata` missing
   entirely → that attempt's `TokenUsage` has all four fields `None`, and
   the outreach's aggregate `cost_tokens`/`estimated_cost_microusd` are
   `NULL`, never `0`.
6. **`thinking_tokens` absence within a present block is a known zero.** A
   mocked `usageMetadata` with `promptTokenCount`/`candidatesTokenCount`/
   `totalTokenCount` but no `thoughtsTokenCount` key produces
   `thinking_tokens == 0`, not `None`.
7. **Mixed-model pricing is never blended.** An outreach with a default-model
   attempt (mocked N1 tokens) and an escalated attempt (mocked N2 tokens, a
   different mocked per-model rate) produces
   `estimated_cost_microusd == price(N1, flash_rate) + price(N2,
   escalation_rate)` — not `(N1+N2) × either single rate`.
8. **Terminal invalid-key call count.** When the default draft's Gemini call
   returns a mocked 403/`INVALID_GEMINI_KEY`, the total number of mocked
   Gemini HTTP calls for the whole `route_and_draft` request is exactly
   `1` — eval and escalation make zero further calls, confirmed by call-count
   assertion, even when the target is high-fit and the workspace is
   opted in.
9. **No silent escalation — no key.** No `gemini` key → heuristic path,
   `0` cost, never escalates, regardless of fit or opt-in.
10. **No silent escalation — no opt-in.** `gemini` key present but
    `paid_tier_enabled` is `False` (including the untouched default for
    every pre-existing workspace) → default-model path only, never
    escalates, even for a fit-100 target.
11. **High-fit threshold is inclusive at the boundary.** With key + opt-in +
    `ESCALATION_MODEL` set and eval below `CONFIDENCE_THRESHOLD`: a target
    at `fit_score = 84` is **not** escalated; a target at `fit_score = 85`
    **is** escalated (exact boundary test, `HIGH_FIT_THRESHOLD = 85`
    inclusive).
12. **Confidence threshold is inclusive at the boundary.** Eligible target,
    default eval `score = 79` → escalates; `score = 80` → early-exit, no
    escalation (`CONFIDENCE_THRESHOLD = 80` inclusive).
13. **Escalation unavailable is never silent.** Key + opt-in + high-fit but
    `ESCALATION_MODEL is None` → no escalation,
    `routing.escalation_unavailable` audited, default draft/eval kept.
14. **Eval uniqueness enforced in SQLite.** A second attempt to insert an
    `eval` row for the same `draft_id` raises the expected `IntegrityError`
    (or the wrapped `EvalAlreadyExists`), and only one `eval` row exists
    for that draft afterward.
15. **Atomic rollback.** If the eval or audit insert fails partway through
    `create_draft_with_routing`, no draft row, no eval row, and no audit
    row are left behind; the one-active-draft-per-target guard and
    `NotFound`/`ActiveDraftExists` behavior are intact.
16. **Paid-tier opt-in is workspace-scoped and defaults off.** A fresh
    workspace (and every pre-existing Slice 1–5 workspace, post-migration)
    has `paid_tier_enabled == False`; enabling it for one workspace does not
    affect any other workspace's value.
17. **Running cost-per-outreach.** `outreach_cost_summary` returns the
    correct average across a workspace's *known-cost* drafts, separately
    reports the count of unknown-cost drafts, and is workspace-scoped
    (another workspace's drafts never leak in).
18. **Tenant isolation.** `eval` rows, cost columns, and
    `paid_tier_enabled` never cross workspaces.
19. **Backward compatibility.** All existing Slice 2–5 tests pass unchanged
    (the `generate_structured` wrapper preserves the old signature and
    `LLMError.usage` defaults to `[]`); an existing business/creator draft
    still drafts and approves exactly as before when no paid tier is
    involved.
20. **Sanitized audit/cost details.** No key ever appears in an eval/
    routing audit detail or a cost string; a rejected-key reason is
    sanitized as in prior slices; a `TokenUsage` never contains anything
    but a model name and plain integers/`None`.
21. **UI wording.** No eval/cost/paid-tier template string contains the word
    "free"; the cost figure is always labelled "estimated paid list-price
    cost"; the corrected Gemini Settings hint no longer mentions
    `GEMINI_API_KEY`.
22. **Heuristic rubric boundary tests (correction 8), one per outcome:**
    personalization (identity absent / present-and-referenced /
    present-and-not-referenced); specificity (evidence present / absent /
    no stored reasons at all); non-genericness (all four combinations of
    the two 0/15 and 0/10 sub-checks); clear-ask (0, 1, and 2+ question
    sentences); missing-body defensive path (`score == 0`, all four
    dimensions `0`).

**Safe live verification (deletable, only if authorized).** No paid live
verification without the owner's explicit authorization (decision 5 of §1).
If the owner authorizes it, a temporary DB-write-free script may make **one**
bounded default-model call to confirm the real `usageMetadata` shape
(including whether `thoughtsTokenCount` is present or absent for this
model), then be deleted (collaboration.md rule 11). The escalation-model
path is verified by mocked tests only unless/until the owner both approves
a specific `ESCALATION_MODEL` and authorizes a bounded paid check — per
decision 6/10, Slice 6 is not marked complete against `SPEC.md` until that
happens, independent of whether this code is merged.

**UI.** Computed-style light/dark checks for the new eval/cost elements;
≤2 final screenshots.

---

## 7. Files touched by the implementation (for reference — not this document)

New: `app/agent/eval.py`, `app/agent/routing.py`,
`tests/test_slice6_eval_routing.py`.
Modified: `app/llm.py`, `app/agent/drafting.py`, `app/models.py`,
`app/db.py`, `app/audit_banners.py`, `app/main.py`,
`app/templates/approvals.html`, `app/templates/pipeline.html`,
`app/templates/campaign_detail.html`, `app/templates/settings.html`,
`PROGRESS.md`, `DECISIONS.md`, `docs/history/COLLABORATION_LOG.md`,
`collaboration.md`. No `requirements.txt` change. Schema changes: new
`eval` table; idempotent `ALTER TABLE` additions for
`workspace.paid_tier_enabled`, `draft.cost_breakdown_json`,
`draft.estimated_cost_microusd`.

**This planning commit** touches only `docs/plans/SLICE_6_PLAN.md`,
`collaboration.md`, and `docs/history/COLLABORATION_LOG.md`.

---

## 8. Remaining assumptions / owner decisions to confirm at review

- **Stronger model id + pricing** are deferred until official availability
  is verified; per decision 6, Slice 6 cannot be marked *complete* against
  `SPEC.md` until the owner approves a specific `ESCALATION_MODEL` and it
  passes a safe verification gate. This is expected to remain open past
  this plan's approval.
- **`gemini-3.6-flash`'s exact current per-million-token input/output/
  thinking rates** (§4.4) are left as explicit placeholders, to be filled
  from the official Gemini pricing page immediately before implementation —
  not fabricated in this plan, and not requiring a paid call to look up.
- **`thoughtsTokenCount`-absent-means-known-zero** (§4.2) is this plan's own
  interpretation of the official API's documented behavior for models
  without extended thinking; flagged in case the owner wants it verified
  against current documentation before implementation rather than accepted
  as stated here.
- **Eval prompt wording** (§5.2) is not fully drafted in this document
  (unlike `drafting.SYSTEM_PROMPT`, which is quoted verbatim) — the exact
  system/user prompt text for the LLM judge is left to implementation,
  constrained by needing to describe the same four 0–25 dimensions the
  heuristic uses.
