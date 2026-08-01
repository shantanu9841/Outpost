# Slice 6 Plan — Evaluation and cost-aware routing (completed)

**Status:** Implemented, tested, and committed on Sonnet per the owner's
authorization of this v4 plan. All §6 acceptance criteria that can be
verified without the stronger escalation model pass (263 retained tests:
212 pre-Slice-6 plus 51 new in `tests/test_slice6_eval_routing.py`).
**Slice 6 is not yet complete against `SPEC.md` §6**: `ESCALATION_MODEL`
remains owner-gated and unset (decision 5/6 below) — see `PROGRESS.md`'s
"Owner-gated: Slice 6 stronger model" section for what that means and what
unblocks it. This document is retained as the implementation's source of
truth; the original "planning only" text below is historical.

**Original status (superseded by the above):** Planning only (draft for
owner review). This is **v4**, correcting three final SDE 2 review findings
against v3 (`4026021`), which followed the v1→v2 and v2→v3 correction
passes — see §0 for the full correction history. No application code,
tests, templates, or schema change is part of this document. Implementation
does not begin until the owner approves this plan, confirms no changes
remain outstanding, and confirms the model switch (`CLAUDE.md`).

**Model:** Planned on **Opus 4.8** (routing/eval architecture is real
judgment). Execution recommendation is **Sonnet** (mechanical implementation
from an approved plan); confirm the switch at the top of implementation.

**Baseline:** branch `codex/sde-1-slice-2-hardening` at `b640b49` (the
committed post-fix Slice 5 state), clean tree, **212 passing tests**
(`python -m unittest discover -s tests`). This plan must be re-confirmed
against that state before coding.

---

## 0. Correction history

### 0.1 v1 → v2 (ten corrections, `2f991a5` → `cc2c23c`)

1. **Strictly workspace-key-only.** Removed the `GEMINI_API_KEY` environment
   fallback from `app/llm.py` — a change to already-shipped Slice 2 code —
   so every LLM workflow is workspace-key-only.
2. **Per-attempt usage records.** Replaced the single-token `LLMResult` with
   `TokenUsage` (model, prompt/input, candidates/output, thinking, total).
3. **Accumulate usage across every attempt.** `generate_structured_with_usage`
   and `LLMError` both carry accumulated usage across the first attempt,
   the retry, and any attempt that falls back to a heuristic.
4. **No silent zero (v2 draft).** Distinguished "no model call was made"
   from "usage is unreadable" — **refined further in §0.2 correction 1**,
   which fixes a remaining gap: v2 still let a failed-but-issued HTTP
   attempt disappear from the usage list entirely, rather than being
   recorded as unknown.
5. **Correct dollar accounting (v2 draft).** Introduced a per-attempt,
   per-token-type breakdown priced at each attempt's own model's rates —
   **corrected further in §0.2 correction 2**, which removes the separate
   "thinking" rate v2 still had.
6. **Terminal invalid-key behavior.** The first rejected-key outcome at any
   model-backed routing stage is terminal for the rest of that request.
7. **Exactly one eval per draft.** The `eval` table declares
   `draft_id INTEGER NOT NULL UNIQUE REFERENCES draft(id)`.
8. **Complete heuristic rubric.** Fully specified all four 0–25 dimensions,
   the shared `BANNED_FILLER_PHRASES` constant, and the exact nested
   Pydantic shapes. Unaffected by this revision.
9. **Corrected billing language.** "Default model" / "estimated paid
   list-price cost" replace "free model" / "free tier" language.
10. **Completion semantics.** Slice 6 cannot be marked complete against
    `SPEC.md` until the stronger model is owner-approved and verified.

Also resolved in v2: paid-tier opt-in storage as a dedicated, idempotently
migrated `workspace.paid_tier_enabled` column, default off.

### 0.2 v2 → v3 (five corrections, `cc2c23c` → `4026021`)

1. **Only "no request issued" may equal zero cost.** §4.2/§4.3/§4.4 are
   corrected so that *every* issued Gemini HTTP attempt — including a
   transport failure, a non-2xx response, a malformed/non-JSON HTTP 200,
   or a 200 with missing/malformed `usageMetadata` — produces a
   `TokenUsage` record with unknown (`None`) fields, rather than silently
   contributing nothing to the usage list. `cost_breakdown = []` /
   `cost_tokens = 0` / `estimated_cost_microusd = 0` is now reserved
   strictly for a workflow that never issued a Gemini request at all (no
   workspace key configured). New acceptance criteria (§6, items 1–6).
2. **Corrected thinking-token pricing.** §4.4/§5.5 remove the separate
   `"thinking"` rate from `PRICING_USD_PER_MILLION_TOKENS` — Google prices
   output inclusive of thinking tokens for these tool-free structured-output
   requests. The dollar formula becomes `input cost = promptTokenCount ×
   input_rate` plus `output cost = (totalTokenCount − promptTokenCount) ×
   output_rate`, requiring known, non-negative `promptTokenCount` and
   `totalTokenCount` with `totalTokenCount >= promptTokenCount`; otherwise
   the estimate is unknown. `candidatesTokenCount`/`thoughtsTokenCount`
   remain stored for visibility but are not required inputs to pricing.
3. **`thoughtsTokenCount` absence is no longer auto-zero.** §4.2 replaces
   v2's "absent key means known zero" rule with: unknown by default, unless
   safely derivable from `total == prompt + candidates` (derived zero) or
   `total > prompt + candidates` (derived non-negative difference, for
   these tool-free calls) — both known. `TokenUsage` gains a
   `thinking_tokens_derived: bool` field so the persisted breakdown can
   distinguish a provider-reported value from a derived one.
4. **Fixed the routing API contradiction.** §5.3 corrects
   `route_and_draft`'s signature — it never receives `workspace_id` yet v2
   called `db.get_paid_tier_enabled(workspace_id)` internally, a
   contradiction. `route_and_draft` now takes `paid_tier_enabled: bool`
   as an explicit keyword argument; `main.py` (§5.7) performs the
   workspace-scoped lookup itself and passes the flag in. Routing performs
   no database access at all.
5. **Header-only Gemini authentication.** §4.6 (new) replaces the
   credential-bearing `?key=` query parameter — carried over unexamined
   from Slice 2 through v1/v2 — with an `x-goog-api-key` request header,
   matching Slice 5's Apify (`Authorization: Bearer`) and YouTube
   (`X-goog-api-key`) precedent. Since Slice 6 already refactors
   `_call_gemini` for the usage/model changes, this correction folds into
   that same refactor rather than being deferred; §2's "out of scope"
   exclusion for this is removed.

### 0.3 v3 → v4 (three corrections, `4026021` → this commit)

1. **Invalid credentials are terminal after every model-backed stage.**
   §5.3 now checks after default drafting, default evaluation, escalated
   drafting, and escalated evaluation. The first
   `INVALID_GEMINI_KEY` outcome prevents every later Gemini request in the
   routing operation, while preserving usage already accumulated and
   completing with the appropriate grounded heuristic result.
2. **Default-model pricing is verified, not placeholder text.** §4.4 records
   the official paid list prices verified on 2026-08-01 for
   `gemini-3.6-flash`: **$1.50 per million input tokens** and **$7.50 per
   million output tokens**, with output including thinking tokens. The
   owner-gated escalation model and its pricing remain deferred.
3. **Decimal pricing and explicit rounding.** §4.4/§5.5 replace binary
   `float` rates and component-wise `round()` with `Decimal` values created
   from strings. Exact per-attempt micro-USD contributions are summed first;
   the outreach total is rounded once to an integer micro-USD using
   `ROUND_HALF_UP`. Boundary tests retain this contract.

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
   *issued* attempt's relevant usage is unreadable, and `0` (known) only
   when **no Gemini request was ever issued at all** (§0.2 correction 1 —
   tightened from v2, which incorrectly let a failed-but-issued attempt
   also collapse to `0`). Historical estimates are computed once at
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
  orchestration, and per-outreach cost accounting/pricing. Takes
  `paid_tier_enabled` as an explicit argument (§0.2 correction 4); performs
  no database access.
- `app/agent/drafting.py` (modified) — exposes `BANNED_FILLER_PHRASES` as a
  real, importable constant (previously only prose inside `SYSTEM_PROMPT`);
  `DraftResult` gains a `usage: list[TokenUsage]` field; `draft_outreach`
  gains an optional `model` parameter so routing can call the escalation
  tier through the same function. No behavior change to the existing
  business/creator drafting logic itself.
- `app/llm.py` (modified) — **removes the `GEMINI_API_KEY` environment
  fallback** (affects every existing caller, not only Slice 6); adds
  `TokenUsage`, `generate_structured_with_usage`, a model-selectable
  request, **and switches Gemini authentication from the `?key=` query
  parameter to the `x-goog-api-key` header** (§0.2 correction 5, §4.6);
  `generate_structured` becomes a thin backward-compatible wrapper.
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
  environment-variable fallback this plan removes). `create_draft` now
  performs the workspace-scoped `paid_tier_enabled` lookup itself and
  passes it into `routing.route_and_draft` (§0.2 correction 4, §5.7).

**Out of scope (unchanged)**

- Re-evaluating a human-edited draft body (eval scores the agent's created
  draft, once — SPEC §4.8). Noted as a limitation.
- Any auto-send/auto-post. Nothing outbound. Escalation never sends
  anything; it only changes which model drafts.
- A second LLM provider. Only Gemini models are used.

(v2 also listed Gemini's `?key=` query-parameter authentication as
out of scope; §0.2 correction 5 brings it into scope, so that exclusion is
removed here.)

---

## 3. Non-negotiables honored

- **BYO-key.** The default model and the stronger tier both use the
  workspace's own `gemini` key exclusively (decision 1) and are billed to
  the workspace owner's Google project. Outpost supplies no key and pays
  for nothing. The key is sent only via the `x-goog-api-key` header
  (§4.6) — never in a request URL or query parameter.
- **Demo mode.** Zero keys → heuristic drafting + heuristic eval + `0` known
  cost; every step completes. This is the **only** genuinely zero-cost path
  — a key present, even for the default model, means real usage against
  that key's quota, whether or not every attempt succeeds.
- **Structured output.** The LLM judge returns a Pydantic-validated
  `EvalResult` with one retry (reusing `llm.py`).
- **Human approval.** Drafting/approval separation is unchanged; eval and
  routing only affect how the *agent* drafts and how the draft is scored.
- **Tenant isolation.** Every `eval`/cost/opt-in read and write is scoped by
  `workspace_id`. `routing.py` itself touches no database — the workspace
  scoping happens once, in `main.py`, before routing is ever called
  (§0.2 correction 4).
- **Atomic audit.** `create_draft_with_routing` commits the draft (with its
  cost columns), its eval row, and every required audit row
  (`draft.created`, `eval.scored`, plus a routing-decision action) in one
  transaction, or none.

---

## 4. Core mechanics (usage, cost, pricing, rubric)

### 4.1 `app/llm.py` — workspace-key-only, no environment fallback

`_resolve_key` changes from `settings.get("gemini") or
os.environ.get("GEMINI_API_KEY")` to strictly `settings.get("gemini")`.
This is a change to code shipped in Slice 2, used by every existing LLM
call site (`intake.py`, `scoring.py`, `drafting.py`) as well as the new
`eval.py`/`routing.py` — every product LLM workflow, not only new Slice 6
code. The module docstring's "Key resolution" paragraph is corrected to
match. `os` becomes an unused import in `llm.py` and is removed.

No other Slice 2–5 behavior changes: a workspace with its own key still
works exactly as before; a workspace with no key still gets `None` from
`generate_structured` and falls back to a heuristic, exactly as today —
only the *environment* variable stops being consulted anywhere.

### 4.2 `TokenUsage` — one record per *issued* attempt, never a silent gap

```python
@dataclass
class TokenUsage:
    model: str
    prompt_tokens: int | None          # usageMetadata.promptTokenCount
    candidates_tokens: int | None      # usageMetadata.candidatesTokenCount
    thinking_tokens: int | None        # usageMetadata.thoughtsTokenCount, or derived
    total_tokens: int | None           # usageMetadata.totalTokenCount
    thinking_tokens_derived: bool = False  # True iff thinking_tokens was
                                            # computed from prompt/candidates/
                                            # total rather than read directly
                                            # from a reported thoughtsTokenCount
```

**Corrected rule (§0.2 correction 1): every issued HTTP attempt produces
exactly one `TokenUsage` record — there is no case where an attempt is
simply omitted from the usage list.** `TokenUsage` is produced by a single
shared, best-effort helper, `_extract_usage(response, model) ->
TokenUsage`, called on **every** response `llm.py` receives back from
Gemini, regardless of status code or body shape:

```python
def _extract_usage(response: httpx.Response, model: str) -> TokenUsage:
    """Never raises. Works identically whether the response was a 200 or
    an error status — an error body is still checked for authoritative
    usageMetadata, in case the provider ever includes it."""
    try:
        body = response.json()
    except (ValueError, TypeError):
        return TokenUsage(model, None, None, None, None)
    if not isinstance(body, dict):
        return TokenUsage(model, None, None, None, None)
    meta = body.get("usageMetadata")
    if not isinstance(meta, dict):
        return TokenUsage(model, None, None, None, None)

    def _nonneg_int(v):
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None

    prompt = _nonneg_int(meta.get("promptTokenCount"))
    candidates = _nonneg_int(meta.get("candidatesTokenCount"))
    total = _nonneg_int(meta.get("totalTokenCount"))
    thinking, derived = _derive_thinking(meta, prompt, candidates, total)
    return TokenUsage(model, prompt, candidates, thinking, total, thinking_tokens_derived=derived)
```

**Population rule per field:**

- `usageMetadata` absent entirely, non-JSON body, or non-dict body/value:
  **all four count fields are `None`** (fully unknown) for that attempt.
  This covers a malformed/incomplete provider response.
- `usageMetadata` present as a dict: `prompt_tokens`, `candidates_tokens`,
  and `total_tokens` each read their documented key only when present and
  a non-negative `int` (not `bool`); otherwise `None`.
- **`thinking_tokens` (§0.2 correction 3 — corrects v2's "absent means
  known zero"):**
  - If `thoughtsTokenCount` is present in `meta`, use it directly (a
    non-negative int, else `None`); `thinking_tokens_derived = False`
    (provider-reported).
  - Else, if `prompt`, `candidates`, and `total` are **all** known and
    `total >= prompt + candidates`: `thinking_tokens = total - prompt -
    candidates` (naturally `0` at the boundary `total == prompt +
    candidates`, and the non-negative difference above it), for these
    tool-free structured-output calls; `thinking_tokens_derived = True`.
  - Otherwise (any of prompt/candidates/total unknown, or `total < prompt
    + candidates`, an internally inconsistent report): `thinking_tokens =
    None` (unknown); `thinking_tokens_derived = False`.

**When is `_extract_usage` called?** On *every* response actually received
from Gemini, before any status-code or body-validity check runs — a
transport-level failure (no response object at all, e.g.
`httpx.RequestError`/timeout) is the **only** case with no response to
extract from, and it still produces a full `TokenUsage(model, None, None,
None, None)` record (§4.3) rather than omitting the attempt.

### 4.3 Accumulation through retries and failures

`generate_structured_with_usage(schema, system, user, settings, *,
model=GEMINI_MODEL) -> MeasuredResult`:

```python
@dataclass
class MeasuredResult:
    value: BaseModel | None    # None only when no workspace key is configured
    usage: list[TokenUsage]    # 0, 1, or 2 entries
```

- **No key configured → `MeasuredResult(None, [])`.** This is the *only*
  case with zero usage entries — no Gemini request was ever issued
  (§0.2 correction 1).
- **`_call_gemini` never returns a bare exception or omits usage.** It
  either returns `(text, TokenUsage)` on a 200 whose body's
  `candidates`/`parts` are successfully extracted, or raises `LLMError`
  with `usage=[<that attempt's TokenUsage>]` attached — for a transport
  failure, a non-2xx status, a malformed/non-JSON 200 body, or a 200 body
  missing the expected `candidates`/`parts` shape. In every one of these
  raise cases, the attached `TokenUsage` reflects `_extract_usage`'s
  best-effort result for that specific attempt (all-unknown for a
  transport failure, since there was no response to extract from; possibly
  partially known for a non-2xx or malformed body, if `_extract_usage`
  happened to find a well-formed `usageMetadata` anyway).
- **The retry loop accumulates every attempt's usage, whichever way it
  resolves:**
  - First attempt raises `LLMError` → re-raise immediately with
    `usage=[usage1]` (one entry — no retry is attempted for a
    transport/status/malformed-body failure, matching the existing
    Slice 2 behavior of only retrying on a schema-validation failure).
  - First attempt succeeds (200, extractable) and validates against the
    schema → `MeasuredResult(parsed, [usage1])`.
  - First attempt succeeds but fails schema validation → retry issued:
    - Retry raises `LLMError` → re-raise with `usage=[usage1, usage2]`
      (both attempts' usage preserved, even though the overall call
      ultimately failed).
    - Retry succeeds and validates → `MeasuredResult(parsed, [usage1,
      usage2])`.
    - Retry succeeds but fails validation again → raise
      `LLMError(ERROR, "model output failed validation twice",
      usage=[usage1, usage2])`.

`LLMError` gains a `usage: list[TokenUsage]` attribute (default `[]`),
populated exactly as above. `TokenUsage` only ever holds a model name,
plain integers/`None`, and one boolean — attaching it to `LLMError` cannot
leak a provider payload, header, URL, or credential, the same guarantee
`LLMError.message` already upholds via `_safe_gemini_reason`.

**Backward compatibility (unchanged from v1/v2's intent):**
`generate_structured(schema, system, user, settings) -> BaseModel | None`
keeps its exact current signature and return type —
`return generate_structured_with_usage(schema, system, user, settings).value`.
Every Slice 2–5 caller and test that calls `generate_structured` or catches
`LLMError` and reads `.kind`/`.message` is unaffected; they never look at
the new `.usage` attribute, which defaults to `[]`.

### 4.4 Cost aggregation, "unknown" vs. "zero", and dollar accounting

A single outreach (one `create_draft` call) can accumulate `TokenUsage`
records from up to four sources: the default draft's model call(s), the
default draft's eval call(s), an escalated draft's model call(s) (only if
escalation actually happened), and the escalated draft's eval call(s).
`routing.py` collects every one of these into one flat
`cost_breakdown: list[TokenUsage]` for the outreach (§5.3), **in the exact
order each attempt was made**, preserving the "known usage from attempts
preceding a failed attempt" requirement — nothing is reordered or dropped
before this list is built.

**Aggregation (§0.2 correction 1, tightened):**

- **`cost_breakdown == []`** — the *only* way this happens is that no
  Gemini request was issued anywhere in the outreach (no `gemini` key at
  all, so drafting and eval both took the pure-heuristic path with zero
  HTTP calls). → `cost_tokens = 0`, `estimated_cost_microusd = 0`. Known
  zero, never ambiguous with "unknown."
- **`cost_breakdown` is non-empty** — at least one Gemini request was
  issued, whether or not it ultimately succeeded:
  - `cost_tokens = sum(u.total_tokens for u in cost_breakdown)` **only if**
    every entry's `total_tokens` is a known int; otherwise `cost_tokens =
    NULL`.
  - `estimated_cost_microusd` is computed by summing each entry's own
    priced contribution (§4.4 dollar estimate, below) **only if** every
    entry prices cleanly; otherwise `estimated_cost_microusd = NULL`. This
    is checked independently of `cost_tokens`'s own known/unknown state
    (a deliberate refinement over v2: an attempt can have a known
    `total_tokens` but an unknown/invalid `prompt_tokens`, in which case
    `cost_tokens` can still be a known number while
    `estimated_cost_microusd` is `NULL` — a token *count* and a token
    *price* are different pieces of information with different
    requirements, and conflating their unknown-ness would be less honest
    than keeping them independent).
  - `cost_breakdown_json` always preserves every attempt's actual
    known/unknown fields individually, regardless of what the aggregates
    show — the detail view can show "default draft: 512 tokens
    (gemini-3.6-flash); eval attempt: usage unknown (non-2xx response)"
    even when the top-line totals are `NULL`, never a fabricated number.

**Dollar estimate formula (§0.2 correction 2 — corrects v2's blended
"thinking" rate; §0.3 corrections 2–3 verify rates and decimal rounding):**

```python
from decimal import Decimal, ROUND_HALF_UP

# app/agent/routing.py — time-sensitive, provider-controlled; re-verify
# against the official Gemini API pricing page before relying on a figure
# (same discipline as Slice 5's Apify/YouTube pricing — SLICE_5_PLAN.md §4.3).
# Only two rates per model: Google prices output inclusive of thinking
# tokens for these tool-free structured-output requests, so there is no
# separate "thinking" rate to configure.
PRICING_USD_PER_MILLION_TOKENS: dict[str, dict[str, Decimal]] = {
    "gemini-3.6-flash": {
        "input": Decimal("1.50"),
        "output": Decimal("7.50"),
    },
    # ESCALATION_MODEL's entry is added once the owner approves that model
    # id and its official pricing is verified (decision 5/6).
}
```

These `gemini-3.6-flash` paid list prices were verified on **2026-08-01**
against Google's official current-model documentation:
<https://ai.google.dev/gemini-api/docs/latest-model>. Reading public pricing
documentation is not a paid API call. Rates remain provider-controlled and
must be re-verified before a later release changes them.

For one `TokenUsage` entry, its priced contribution requires
`prompt_tokens` and `total_tokens` both known, non-negative, and
`total_tokens >= prompt_tokens` (re-validated defensively at pricing time,
independent of whatever `_extract_usage` already enforced — the same
"defense in depth beyond the producer's own guarantee" discipline
`scoring.assert_grounded` already uses), and `model` present in
`PRICING_USD_PER_MILLION_TOKENS`:

```
attempt_cost_microusd = (
    Decimal(prompt_tokens) * input_rate
    + Decimal(total_tokens - prompt_tokens) * output_rate
)

# Sum every exact Decimal attempt contribution first, then round once.
estimated_cost_microusd = int(
    total_exact_microusd.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
)
```

(`input_rate`/`output_rate` are USD per **million** tokens; a microUSD is
1e-6 USD, so `tokens × (USD per 1e6 tokens)` already equals the cost in
microUSD directly — no further unit conversion factor is needed. This is
worth stating explicitly in the implementation so the `1_000_000` doesn't
get applied twice or inverted.) Rates are constructed from strings as
`Decimal`, never binary floats. `candidates_tokens`/`thinking_tokens` are
**not** read for pricing at all — they remain in `TokenUsage` purely for
display/visibility (§0.2 correction 2), never required or consulted by
`_price`.

Any entry that fails the prompt/total validity check makes the **whole
outreach's** `estimated_cost_microusd` `NULL` — one bad entry cannot be
silently skipped and the rest summed, since that would understate cost
without saying so.

`estimated_cost_microusd` is an integer count of millionths of a US dollar
computed with explicit decimal arithmetic and one final `ROUND_HALF_UP`, so
the stored figure has no binary-floating-point drift. A later pricing-table
change cannot retroactively alter a historical draft's stored estimate —
only future drafts see a new rate.

**Billing language:** "default model" replaces "free model"/"free tier"
everywhere in this plan and in the UI copy it specifies (§5.7). Default
drafting and the LLM judge both consume the workspace owner's own Gemini
quota and **may incur real charges** the moment a `gemini` key is present,
regardless of whether escalation ever fires or whether every attempt
succeeds. The UI always labels the dollar figure "estimated paid list-price
cost," never implying it is free or discounted. The only workspace state
that is genuinely zero-cost is no `gemini` key at all.

### 4.5 The complete deterministic heuristic rubric

Unchanged by this revision — carried forward verbatim from v2.

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

**`EvalDimension` — the exact Pydantic shape for a justification:**

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
re-derived from the draft's own claimed citation.

- `reasons = drafting._parse_fit_reasons(target)`; if empty → **0 points**
  (defensive only). Justification: `"No stored evidence was available to
  check for a specific detail."`
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
  `len(set(lengths)) > 1` → **10**; otherwise → **0**.
- `points = banned_phrase_points + variety_points`.

**Dimension 4 — `clear_ask` (0–25):** `question_count = sum(1 for s in
_sentences(body) if s.rstrip().endswith("?"))`.

- `question_count == 1` → **25 points**.
- `question_count == 0` → **0 points**.
- `question_count >= 2` → **10 points**.

**Missing-data behavior:** if `draft_body` is blank/empty (defensive
only), every dimension scores `0`; `score = 0`.

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

### 4.6 Gemini header authentication (§0.2 correction 5, new)

`app/llm.py` as shipped in Slices 2–5 sends the API key as a `key=` query
parameter (`httpx.post(GEMINI_URL, params={"key": api_key}, ...)`) —
credential-bearing URLs are exactly what Slice 5 corrected for Apify and
YouTube, and Slice 6 already has to touch `_call_gemini` for the
usage/model changes above, so this correction folds the same fix in here
rather than leaving it for a future slice.

- `_url(model) -> str` returns
  `f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"`
  — no query string at all.
- The request becomes `httpx.post(_url(model), headers={"x-goog-api-key":
  api_key}, json=body, timeout=REQUEST_TIMEOUT_SECS)` — `params=` is
  removed entirely from this call.
- **No request URL or query parameter ever contains the key**, matching
  the exact guarantee Apify/YouTube already provide.
- Sanitization is unchanged in spirit but re-stated precisely: an echoed
  key inside an error message body is still redacted by
  `_safe_gemini_reason` (`message.replace(api_key, "[REDACTED]")`) as
  defense-in-depth, exactly as it does today — this is not weakened by
  moving the key out of the URL, it is additional to it.

---

## 5. Architecture

### 5.1 `llm.py` — measured calls, selectable model, header auth, no env fallback

`GEMINI_MODEL` stays the default-model constant; `_url(model)` replaces the
hardcoded `GEMINI_URL` (§4.6). `_call_gemini(api_key, system, user,
response_schema, model)`:

- Issues the POST with the `x-goog-api-key` header (§4.6).
- On `httpx.RequestError`: raises `LLMError(ERROR, "could not reach Gemini
  (...)", usage=[TokenUsage(model, None, None, None, None)])` — one
  unknown-usage entry, never omitted (§4.2/§4.3).
- Otherwise calls `_extract_usage(response, model)` **once**, on the raw
  response, before any status-code check.
- On a non-2xx status: raises the existing classified `LLMError` (via
  `_to_llm_error`, unchanged classification logic) with that response's
  `_extract_usage` result attached as `usage=[...]`.
- On a 200 whose body isn't valid JSON: raises `LLMError(ERROR, "Gemini
  returned a non-JSON response", usage=[...])` with the same
  `_extract_usage` result (almost always all-`None`, since a non-JSON body
  can't contain `usageMetadata` either, but computed via the identical
  path rather than special-cased).
- On a 200 whose JSON lacks the expected `candidates`/`parts` shape:
  raises `LLMError(ERROR, ..., usage=[...])`, same pattern.
- Only on a 200 with successfully extracted text does it return
  `(text, usage)` — never raising.

`generate_structured_with_usage` performs the two-shot retry loop from
§4.3, accumulating `usage_log` from every `LLMError.usage`/successful-call
usage it sees, in order. `generate_structured` is the thin
backward-compatible wrapper from §4.3.

### 5.2 `eval.py` — rubric scoring (LLM judge + fully-specified heuristic)

Unchanged from v2. `evaluate_draft`: if `known_invalid_key_reason` is set,
skip the live call entirely and return the heuristic result with
`status=INVALID_GEMINI_KEY` and `usage=[]` (mirrors
`scoring.score_batch`'s existing short-circuit). Otherwise call
`llm.generate_structured_with_usage(EvalResult, SYSTEM_PROMPT_EVAL,
_build_eval_prompt(brief, target, draft_body), settings)`; on `LLMError`,
fall back to the heuristic but **keep the error's `usage`** so tokens spent
on a failed judge attempt are never silently dropped. On success, use the
LLM's `EvalResult` and its usage. On no key (`value is None`), fall back to
the heuristic with `usage=[]`.

### 5.3 `routing.py` — tier decision, terminal invalid-key, early-exit, cost

```python
HIGH_FIT_THRESHOLD = 85       # inclusive
CONFIDENCE_THRESHOLD = 80     # inclusive
ESCALATION_MODEL: str | None = None  # unset until owner-verified (decision 5/6)
```

**Corrected signature (§0.2 correction 4 — fixes v2's contradiction):**

```python
def route_and_draft(
    brief: Brief,
    target: dict,
    settings: dict[str, str],
    *,
    paid_tier_enabled: bool,
) -> RoutingOutcome: ...
```

v2's draft signature was `route_and_draft(brief, target, settings) ->
RoutingOutcome`, yet its escalation-eligibility step called
`db.get_paid_tier_enabled(workspace_id)` — a `workspace_id` the function
never received. `routing.py` now takes the already-resolved boolean as an
explicit keyword argument and **performs no database access of any kind**;
the workspace-scoped lookup happens exactly once, in `main.py` (§5.7),
before `route_and_draft` is ever called. This keeps the tenant-isolation
guarantee ("every read/write scoped by `workspace_id`") anchored at the
one call site that actually has a `workspace_id` in scope, rather than
letting it leak into a module that otherwise has no database dependency at
all.

Called by `create_draft` in place of the direct `draft_outreach` call:

1. **Default draft.** `drafting.draft_outreach(brief, target, settings)` —
   heuristic if no key, default model if key present. Collect its `usage`.
2. **Terminal check after default drafting.** If the default draft's `status
   == DraftStatus.INVALID_GEMINI_KEY`:
   - Evaluate its grounded heuristic body with `known_invalid_key_reason`
     set (§5.2), which issues **no** judge request.
   - Force escalation ineligible, audit `routing.invalid_key_terminal`
     with sanitized detail naming `default_draft`, and skip to cost.
3. **Evaluate the default draft.** Call `eval.evaluate_draft(brief, target,
   default_body, settings)` and collect its `usage`. If the returned
   `EvalStatus == INVALID_GEMINI_KEY`, keep the default body and its
   heuristic eval result, audit `routing.invalid_key_terminal` with
   sanitized detail naming `default_eval`, and skip escalation entirely.
4. **Escalation eligibility (only after both terminal checks pass):**
   `settings.get("gemini")` present **and** `paid_tier_enabled` (the
   parameter, not a lookup) **and** `target["fit_score"] >=
   HIGH_FIT_THRESHOLD` **and** `ESCALATION_MODEL is not None`.
   - Not eligible for an ordinary reason → keep the default draft/eval, no
     extra routing audit.
   - Eligible on key + opt-in + fit but `ESCALATION_MODEL is None` → keep
     default and audit `routing.escalation_unavailable`.
5. **Confidence early-exit / escalation with terminal checks.**
   - Default eval `score >= CONFIDENCE_THRESHOLD` → keep the default
     draft and audit `routing.early_exit`.
   - Otherwise call `drafting.draft_outreach(...,
     model=ESCALATION_MODEL)` and collect its usage.
   - If escalated drafting returns `INVALID_GEMINI_KEY`, issue **no**
     escalated-eval request; retain the already-valid default body/eval,
     audit `routing.invalid_key_terminal` with sanitized detail naming
     `escalated_draft`, and skip to cost.
   - Otherwise evaluate the escalated body and collect the evaluator's usage.
     If that evaluator returns `INVALID_GEMINI_KEY`, make no later Gemini
     call, keep the escalated body with its deterministic fallback eval, and
     audit `routing.invalid_key_terminal` with sanitized detail naming
     `escalated_eval`. Otherwise keep the escalated body/eval/model and
     audit `routing.escalated`.
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
    cost_tokens: int | None            # None means unknown, 0 means no request issued
    estimated_cost_microusd: int | None
    routing_action: str  # "default" | "early_exit" | "escalated"
                          # | "escalation_unavailable" | "invalid_key_terminal"
```

All thresholds, `ESCALATION_MODEL`, and `PRICING_USD_PER_MILLION_TOKENS`
are named module constants, easy for the owner to adjust.

### 5.4 `drafting.py` changes (unchanged from v2)

- `BANNED_FILLER_PHRASES` constant added (§4.5); `SYSTEM_PROMPT`'s existing
  prose is left as-is with a comment tying the two together.
- `DraftResult` gains `usage: list[TokenUsage] = field(default_factory=
  list)` as a fifth, defaulted field.
- `draft_outreach(brief, target, settings, *, known_invalid_key_reason=None,
  model=GEMINI_MODEL)` gains the optional `model` parameter, threaded to
  `generate_structured_with_usage`.

### 5.5 Cost/pricing computation helper (corrected formula)

A pure function in `routing.py`,
`_price(cost_breakdown: list[TokenUsage]) -> tuple[int | None, int | None]`,
returning `(cost_tokens, estimated_cost_microusd)` per §4.4's now-decoupled
rules:

```python
def _price(cost_breakdown: list[TokenUsage]) -> tuple[int | None, int | None]:
    if not cost_breakdown:
        return 0, 0

    cost_tokens = None
    if all(u.total_tokens is not None for u in cost_breakdown):
        cost_tokens = sum(u.total_tokens for u in cost_breakdown)

    exact_microusd = Decimal("0")
    for usage in cost_breakdown:
        rates = PRICING_USD_PER_MILLION_TOKENS.get(usage.model)
        if (
            usage.prompt_tokens is None or usage.total_tokens is None
            or usage.prompt_tokens < 0 or usage.total_tokens < usage.prompt_tokens
            or rates is None
        ):
            return cost_tokens, None
        exact_microusd += (
            Decimal(usage.prompt_tokens) * rates["input"]
            + Decimal(usage.total_tokens - usage.prompt_tokens) * rates["output"]
        )

    estimated_cost_microusd = int(
        exact_microusd.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return cost_tokens, estimated_cost_microusd
```

Unit-testable independent of any HTTP mocking, which is how the corrected
"unknown usage," "mixed-model pricing," and "cost-tokens-vs-dollar-estimate
decoupling" acceptance criteria (§6) are verified precisely.

### 5.6 `db.py` — eval table, paid-tier column, cost columns, atomic creation

Unchanged from v2.

**Paid-tier opt-in:** a dedicated, idempotently migrated boolean column on
`workspace`:

```sql
ALTER TABLE workspace ADD COLUMN paid_tier_enabled INTEGER NOT NULL DEFAULT 0
```

guarded by a small `_add_column_if_missing(conn, table, column, ddl)`
helper (checked via `PRAGMA table_info(table)`). The same helper adds
`draft`'s two new columns:

```sql
ALTER TABLE draft ADD COLUMN cost_breakdown_json TEXT
ALTER TABLE draft ADD COLUMN estimated_cost_microusd INTEGER
```

Default `0` makes every existing workspace opted **out** automatically.
`get_paid_tier_enabled(workspace_id) -> bool` and
`set_paid_tier_enabled(workspace_id, enabled: bool) -> None` are the only
functions that ever read/write this column — both live in `db.py`, called
from `main.py` (§5.7), **never** from `routing.py` (§0.2 correction 4).

**`eval` table** (exactly one per draft, SPEC §3, idempotent):

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
draft" guarantee at the database level.

**Atomic creation:**

```python
def create_draft_with_routing(
    workspace_id: int, target_id: int, outcome: RoutingOutcome, actor: str = "agent",
) -> int:
    """Insert the draft (with its cost columns), its eval row, and every
    required audit row in one transaction."""
```

**Read helpers:** `get_eval_for_draft(workspace_id, draft_id)`, and
`outreach_cost_summary(workspace_id)` (known-cost average, unknown-cost
count, draft count).

### 5.7 `main.py` + templates

- **Corrected wiring (§0.2 correction 4):** `create_draft` first resolves
  `paid_tier_enabled = db.get_paid_tier_enabled(workspace_id)` (the same
  `workspace_id` already in scope from `get_current_workspace`), then calls
  `routing.route_and_draft(brief, dict(target), settings,
  paid_tier_enabled=paid_tier_enabled)`, then
  `db.create_draft_with_routing(workspace_id, target_id, outcome)`. Its
  existing redirects/guards are unchanged.
- **Approvals** (`approvals.html`): each draft card shows model used, an
  eval score badge (four-dimension rubric with justifications on expand),
  and cost — `"N tokens · ~$X.XXXX estimated paid list-price cost"` when
  known, `"cost unknown"` when not, `"0 tokens (heuristic, no cost)"` when
  no key was ever used. A header strip shows the running cost-per-outreach
  average (excluding unknown-cost drafts, with a visible count of how many
  are excluded).
- **Pipeline** / **campaign detail:** lighter — eval score + cost shown per
  card/row where a draft exists; no new controls.
- **Settings** (`settings.html`): (a) a checkbox "Enable the stronger paid
  model tier for high-fit outreach — uses *your* Gemini key; your Google
  project is billed for both the default and stronger tiers," disabled/
  greyed with a hint when no `gemini` key is saved; (b) the existing Gemini
  key-card hint is corrected — current copy references the removed
  environment fallback. New copy: "Required for the default and
  stronger-tier model calls; without a key, Outpost uses its built-in demo
  heuristic at zero cost." No "free" language anywhere.
- Reuse existing design tokens only; no new colors/spacing.

---

## 6. Verification and acceptance criteria

Proportional to risk (collaboration.md rule 9). Baseline: the Slice 5
retained suite (212 tests) still passes, plus new
`tests/test_slice6_eval_routing.py` (mocked at the `llm`/`httpx` boundary —
no live call, no real key, temp SQLite).

**§0.2 correction 1 — every issued attempt is recorded:**

1. **No request issued produces known zero.** No `gemini` key configured →
   `MeasuredResult(None, [])`; a fully heuristic outreach →
   `cost_breakdown == []`, `cost_tokens == 0`, `estimated_cost_microusd ==
   0`, `cost_breakdown_json == "[]"`.
2. **A transport failure after request issuance produces unknown cost.** A
   mocked `httpx.RequestError` on the only attempt → `LLMError.usage ==
   [TokenUsage(model, None, None, None, None)]` (one entry, not zero); the
   outreach's `cost_tokens`/`estimated_cost_microusd` are `NULL`, not `0`.
3. **A non-2xx response produces unknown cost unless authoritative usage is
   present.** (a) A mocked 403/500 with no `usageMetadata` in the error
   body → that attempt's `TokenUsage` is all-`None`, aggregate unknown. (b)
   A mocked non-2xx response whose body *does* contain a well-formed
   `usageMetadata` → that attempt's known fields are used, proving the
   extraction path is genuinely shared between success and error responses,
   not special-cased to always return unknown for non-2xx.
4. **A malformed/non-JSON HTTP 200 produces an unknown attempt and
   preserves earlier known attempts.** A mocked first-attempt-invalid
   (well-formed usage, fails schema validation) followed by a
   retry that returns a non-JSON 200 body → `usage == [usage1 (known),
   usage2 (all-None)]`, attached to the raised `LLMError`; the outreach's
   `cost_breakdown_json` still shows attempt 1's real numbers even though
   the aggregate is unknown.
5. **Missing/malformed `usageMetadata` produces unknown usage.** A 200 with
   a well-formed JSON body but no `usageMetadata` key (or a non-dict value
   for it) → all four `TokenUsage` fields `None`.
6. **Retry usage preserves every attempt in order.** A mocked
   first-attempt-invalid, second-attempt-valid sequence produces
   `MeasuredResult.usage` with exactly two entries in call order.

**§0.2 correction 2 — corrected pricing formula:**

7. **Pricing uses prompt tokens at the input rate and all remaining total
   tokens at the output rate, with one final rounding step.** For each
   `TokenUsage(prompt_tokens=P, total_tokens=T, ...)`, `_price` adds
   `Decimal(P) × input_rate + Decimal(T − P) × output_rate` to an exact
   outreach-level Decimal accumulator. It rounds that accumulator exactly
   once with `ROUND_HALF_UP`. It never reads `candidates_tokens` or
   `thinking_tokens` for pricing. Boundary fixtures immediately below,
   exactly at, and immediately above a half-microUSD prove the rounding rule
   and prove component-wise/per-attempt rounding is not used.
8. **The verified default pricing table is exact and has no thinking rate.**
   A structural test asserts the `gemini-3.6-flash` entry contains only
   `input=Decimal("1.50")` and `output=Decimal("7.50")`, and that
   no per-model dict contains a `"thinking"` key.
9. **Mixed-model pricing is never blended or prematurely rounded.** An
   outreach with default-model and escalation-model attempts uses each
   attempt's own Decimal rate pair, sums all exact contributions, and rounds
   the combined result once — never a blended rate, the final model's rate
   on the combined tokens, or a sum of already-rounded attempt costs.
10. **Invalid prompt/total combinations make the estimate unknown, not
    silently skipped.** `total_tokens < prompt_tokens`, a negative
    `prompt_tokens`, or a `model` absent from the pricing table each make
    `estimated_cost_microusd` (for the whole outreach) `NULL` — confirmed
    it is not simply omitted from a sum, which would understate cost.
11. **`cost_tokens` and `estimated_cost_microusd` can be independently
    unknown.** A crafted `TokenUsage` with a known `total_tokens` but an
    unknown `prompt_tokens` produces a known `cost_tokens` alongside a
    `None` `estimated_cost_microusd` — proving the two aggregates are not
    force-coupled.

**§0.2 correction 3 — thinking-token derivation:**

12. **Missing `thoughtsTokenCount` does not automatically become zero.** A
    mocked `usageMetadata` with `promptTokenCount`/`candidatesTokenCount`/
    `totalTokenCount` but no `thoughtsTokenCount` key, where
    `total < prompt + candidates` (an inconsistent report) → `thinking_
    tokens is None`, `thinking_tokens_derived is False`.
13. **Derived-zero boundary.** Same setup but `total == prompt +
    candidates` → `thinking_tokens == 0`, `thinking_tokens_derived is
    True`.
14. **Derived-difference boundary.** Same setup but `total > prompt +
    candidates` → `thinking_tokens == total - prompt - candidates`,
    `thinking_tokens_derived is True`.
15. **Provider-reported takes priority over derivation.** A mocked
    `usageMetadata` with an explicit `thoughtsTokenCount` present (even if
    it wouldn't match what the derivation formula would compute) → that
    literal value is used, `thinking_tokens_derived is False`.

**§0.2 correction 4 — routing signature fix:**

16. **`main.py` passes a workspace-scoped `paid_tier_enabled` boolean into
    routing.** A test asserts `create_draft`'s route calls
    `db.get_paid_tier_enabled(workspace_id)` for the request's own
    workspace and forwards the exact result into
    `routing.route_and_draft(..., paid_tier_enabled=...)`.
17. **Routing performs no database lookup.** A test calls
    `routing.route_and_draft` directly (mocking only `llm`/`httpx`, never
    `app.db`) and confirms it completes without any `app.db` function
    being invoked — proving routing is a pure function of its arguments.

**§0.2 correction 5 — header-only Gemini authentication:**

18. **Gemini sends the key only through `x-goog-api-key`.** Every mocked
    `httpx.post` call made by `llm.py` carries
    `headers["x-goog-api-key"] == <the workspace key>`.
19. **Request URLs and query parameters contain no credential.** The same
    mocked calls' first positional argument (the URL) never contains the
    key string, and the call's `params` kwarg (if present at all) never
    contains a `"key"` entry.

**Carried forward from v2, still required:**

20. **No silent escalation — no key / no opt-in.** No `gemini` key →
    heuristic path, `0` cost, never escalates. `gemini` key present but
    `paid_tier_enabled=False` → default-model path only, never escalates,
    even for a fit-100 target.
21. **High-fit / confidence thresholds are inclusive at both boundaries.**
    `fit_score = 84` not escalated, `fit_score = 85` escalated
    (`HIGH_FIT_THRESHOLD`); eligible target with default eval `score = 79`
    escalates, `score = 80` early-exits (`CONFIDENCE_THRESHOLD`).
22. **Invalid credentials are terminal after every model-backed stage.**
    Retained call-count cases cover: (a) invalid default draft → exactly one
    Gemini call; (b) successful default draft then invalid default eval →
    exactly two calls and no escalation; (c) successful default draft/eval
    then invalid escalated draft → exactly three calls and no escalated eval;
    and (d) invalid escalated eval → no later Gemini call. Every case retains
    usage already accumulated, completes through the specified grounded
    fallback, and audits `routing.invalid_key_terminal` with the sanitized
    stage name.
23. **Escalation unavailable is never silent.** Key + opt-in + high-fit but
    `ESCALATION_MODEL is None` → no escalation,
    `routing.escalation_unavailable` audited, default draft/eval kept.
24. **Eval uniqueness enforced in SQLite.** A second attempt to insert an
    `eval` row for the same `draft_id` raises the expected
    `IntegrityError`/`EvalAlreadyExists`; only one `eval` row exists for
    that draft afterward.
25. **Atomic rollback.** If the eval or audit insert fails partway through
    `create_draft_with_routing`, no draft row, no eval row, and no audit
    row are left behind.
26. **Paid-tier opt-in is workspace-scoped and defaults off.** A fresh
    workspace (and every pre-existing Slice 1–5 workspace, post-migration)
    has `paid_tier_enabled == False`; enabling it for one workspace does
    not affect any other workspace's value.
27. **Tenant isolation.** `eval` rows, cost columns, and
    `paid_tier_enabled` never cross workspaces.
28. **Backward compatibility.** All existing Slice 2–5 tests pass unchanged;
    an existing business/creator draft still drafts and approves exactly as
    before when no paid tier is involved.
29. **Sanitized errors, audit details, and cost breakdowns never expose the
    key or headers.** No key ever appears in an eval/routing audit detail,
    a cost string, a `TokenUsage`, or `cost_breakdown_json`; a
    rejected-key reason is sanitized as in prior slices.
30. **UI wording.** No eval/cost/paid-tier template string contains the
    word "free"; the cost figure is always labelled "estimated paid
    list-price cost"; the corrected Gemini Settings hint no longer
    mentions `GEMINI_API_KEY`.
31. **Environment key cannot trigger drafting, evaluation, or escalation.**
    With `GEMINI_API_KEY` set in `os.environ` and no workspace `gemini`
    key: drafting takes the heuristic path; `eval.evaluate_draft` returns
    `EvalStatus.NO_GEMINI_KEY`; routing never escalates even with
    `paid_tier_enabled=True` and a high-fit target.
32. **Heuristic rubric boundary tests**, one per outcome: personalization
    (identity absent / present-and-referenced / present-and-not-referenced);
    specificity (evidence present / absent / no stored reasons at all);
    non-genericness (all four combinations of the two sub-checks);
    clear-ask (0, 1, and 2+ question sentences); missing-body defensive
    path.

**Safe live verification (deletable, only if authorized).** No paid live
verification without the owner's explicit authorization (decision 5 of
§1). If the owner authorizes it, a temporary DB-write-free script may make
**one** bounded default-model call to confirm the real `usageMetadata`
shape (including whether `thoughtsTokenCount` is present or absent for
this model, to sanity-check the derivation rule in §4.2 against a live
response), then be deleted (collaboration.md rule 11). The escalation-model
path is verified by mocked tests only unless/until the owner both approves
a specific `ESCALATION_MODEL` and authorizes a bounded paid check — per
decision 6, Slice 6 is not marked complete against `SPEC.md` until that
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

- **The `thoughtsTokenCount`-derivation rule** (§4.2/§0.2 correction 3) is
  this plan's own interpretation of safe derivation for tool-free
  structured-output calls; flagged in case the owner wants the "safe live
  verification" script (§6) to specifically confirm whether real
  `gemini-3.6-flash` responses ever report `thoughtsTokenCount` at all, and
  if not, whether the `total == prompt + candidates` boundary actually
  holds in practice.

- **Eval prompt wording** (§5.2) is not fully drafted in this document —
  left to implementation, constrained by needing to describe the same four
  0–25 dimensions the heuristic uses.
