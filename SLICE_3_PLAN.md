# Slice 3 Plan — Fit-scoring with citations (corrected)

Plan for Slice 3 (SPEC.md §6). This document is the single source of truth for
Slice 3's design. No implementation has started — this revision touches only
`SLICE_3_PLAN.md` (and, at commit time, a `collaboration.md` log entry).

This is **v2** of the plan. It supersedes the original after an owner review
that approved the overall direction (discovery-time scoring, deterministic
fallback, stored results, explicit audit mapping, the weak demo target) but
required seven corrections before implementation. Section 0.1 maps each
correction to where it is resolved.

## 0. Collaboration & model status

- **SDE 1** created the original plan; this v2 is the owner-directed correction.
  Two design forks were already decided: (1) fit-scoring runs **at discovery
  time**; (2) a **deliberately weak seed company** is added so the no-key demo
  always shows a visible sub-70 score.
- One further fork was decided in this review: target scoring uses **one batch
  LLM call** (a single `FitBatch` response covering all targets), not a
  per-target loop — see §5 and §6. This is what makes the honest-aggregate
  (#4), bounded-latency, and single-transaction (#5) requirements fall out
  cleanly.
- Planning/correction was done on the stronger reasoning model (Opus).
  Recommended **execution model: Sonnet** — this slice is mechanical execution
  from a settled plan. Stated again at the top of implementation so the owner
  can confirm the switch before code begins (CLAUDE.md).
- **Precondition (correction #1):** Slice 2 hardening is complete and committed
  (`b6aa26e` on `codex/sde-1-slice-2-hardening`, working tree clean, all 32
  tests green). Collaboration rules are satisfied — no uncommitted Slice 2 work
  remains. Slice 3 implementation begins on top of that committed state (branch
  choice — continue here vs. after a merge to `main` — is the owner's call and
  is confirmed before code begins, per collaboration.md rule 6).
- Non-negotiables in play (CLAUDE.md): #2 demo mode always completes (scoring
  must work with zero keys), #4 every action audited, #5 structured output
  validated with retry, #6 workspace isolation, plus the `Local data` rule
  (no reset/delete of `outpost.db` or seeds) and the `Collaboration` rule.

### 0.1 Corrections applied in v2

| # | Owner correction | Resolved in |
|---|---|---|
| 1 | Finish Slice 2 hardening first | Precondition above — already committed, tree clean |
| 2 | Citations must be grounded, not just non-empty | §3 (schema: `evidence_key`/`evidence_value`, non-empty `reason`) + §4.2 (grounding verified against the supplied evidence before storing) |
| 3 | Normalize evidence before scoring; use the `Source.evidence()` boundary | §4.1 (source-neutral evidence shape, each source owns its normalization; scoring never sees provider keys) |
| 4 | Batch status must be honest, not assumed uniform; stop after terminal credential failure | §4.2 (explicit aggregate counts/status) + §6 (one call ⇒ a credential failure is a single 403, never a retry loop) |
| 5 | Synchronous latency too risky; one transaction; define zero-target case | §5 (single batch call) + §6 (compute-all-then-persist in one DB transaction; explicit zero-target branch) |
| 6 | Verification is stale; add retained tests; the 6-target assertion breaks | §11 (retained `tests/test_slice3_scoring.py`; the Slice 2 seed-count test is updated, listed in §11's file list, with the seed addition itself in §10) |
| 7 | Make heuristic precise; require an accessible caret with `aria-expanded` + keyboard support | §4.3 (exact weights, normalization, missing-field rules, canonical brief with anchor scores) + §9 (real `<button>` caret, `aria-expanded`, native keyboard) |

**v2.1 review refinements** (second owner pass):

| Refinement | Resolved in |
|---|---|
| `_is_grounded` must reject `None`/blank evidence values, not just missing keys | §4.2 (grounding rule 2) + §11 test 2(c) |
| `add_scored_targets` must guard `len(candidates) == len(scores)` before the transaction; mismatch raises, writes zero rows | §7 (guard-first) + §11 test 8 length-guard |
| Retained tests for missing / duplicate / out-of-range `target_index` (§4.2 promises the behavior) | §11 test 6 |
| One **live** Gemini batch verification (stored rotated key, never read) — mocks can't prove Gemini accepts the nested `FitBatch` schema | §11.2 live-Gemini-batch step |

---

## 1. Goal and done-when (SPEC.md §6)

For each discovered target, pull evidence and score fit 0–100 with reasons that
**cite specific evidence that is verified to exist in that evidence**. Structured
output validated, retry on bad parse, **no score without at least one grounded
citation**. Fit coloring per design.md (≥85 `success`, 70–84 `text`, <70
`text-3`).

**Done when:** the discovery table shows a fit score and, on expand (via an
accessible caret), cited reasons for each target; a deliberately weak target
scores low with honest, grounded reasons; and this holds on the zero-key demo
path, not only with a live LLM.

---

## 2. What already exists (reused unchanged)

- `target` table already carries `fit_score INTEGER` and `fit_reasons_json TEXT`
  (added in Slice 2's schema for exactly this slice) — **no migration needed**.
- `Source.evidence(candidate) -> dict` is defined on the interface. In Slice 2
  it returned `candidate.raw` verbatim; Slice 3 upgrades it to return a
  **normalized** shape (§4.1) — that is the whole point of correction #3.
- `llm.generate_structured(schema, system, user, settings)` already does the
  two-shot, schema-aware retry, sends `responseJsonSchema` for server-side
  enforcement, and raises `LLMError(kind=...)` distinguishing a rejected
  credential (`INVALID_KEY`) from every other failure (`ERROR`), or returns
  `None` when no key is configured anywhere. **No `llm.py` change is needed** —
  batch scoring is just a call with a `FitBatch` schema.
- `campaign_detail` is a pure read that re-derives banners from the audit trail
  via `audit_banners.banner_for(...)`. Slice 3 keeps it a pure read.
- `audit_banners.BANNER_BY_ACTION` is derived by iterating the status maps, so
  adding a third map wires banners automatically.

---

## 3. Structured-output schema (`app/models.py`)

Correction #2: a citation must point at a **named evidence field and its
value**, and the `reason` itself must be non-empty. The schema enforces
*shape*; §4.2 enforces *truth* (that the cited field/value actually appear in
the evidence) — a schema can't see runtime evidence, so grounding lives in
`scoring.py`, right after validation and before any write.

```python
from pydantic import BaseModel, field_validator, model_validator


class FitReason(BaseModel):
    reason: str          # why this evidence moves the score
    evidence_key: str    # a field name present in the normalized evidence
    evidence_value: str  # that field's value, quoted verbatim (stringified)

    @field_validator("reason", "evidence_key", "evidence_value")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason, evidence_key, and evidence_value are all required")
        return v


class FitAssessment(BaseModel):
    target_index: int          # which target in the batch this scores
    fit_score: int
    reasons: list[FitReason]

    @field_validator("fit_score")
    @classmethod
    def in_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("fit_score must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def at_least_one_reason(self) -> "FitAssessment":
        if not self.reasons:
            raise ValueError("a fit score requires at least one cited reason")
        return self


class FitBatch(BaseModel):
    """One structured response scoring every target in the batch at once."""

    assessments: list[FitAssessment]
```

The schema guarantees: every reason names a field and quotes a value (all
non-empty), and every assessment has ≥1 reason and an in-range score. What it
cannot guarantee — that `evidence_key`/`evidence_value` are *true* — is checked
in §4.2. Between the two, there is no code path that stores a score with an
empty, or a fabricated, citation.

---

## 4. Scoring module (`app/agent/scoring.py`)

### 4.1 Source-neutral evidence (correction #3)

Scoring never reads provider-specific keys. Each source owns the translation
from its raw payload to one **normalized evidence shape**, exposed through the
`Source.evidence()` boundary:

```python
# normalized evidence shape (the ONLY thing scoring reads)
{
    "name":      str,          # always present
    "industry":  str | None,
    "employees": int | None,   # apollo: estimated_num_employees; seed: employees
    "country":   str | None,
    "domain":    str | None,
}
```

Implementation:

- `app/sources/apollo.py`: add `normalize_evidence(raw: dict) -> dict` mapping
  `estimated_num_employees → employees`, `name`, `industry`, `country`,
  `primary_domain → domain`. `ApolloSource.evidence()` delegates to it.
- `app/sources/seed.py`: add `normalize_evidence(raw: dict) -> dict` mapping
  `employees → employees`, `name`, `industry`, `country`, `domain`.
  `SeedSource.evidence()` delegates to it.
- `app/sources/__init__.py`: add a dispatcher
  `evidence_for(source_used: str, candidate: Candidate) -> dict` that routes to
  the right source's normalizer by `source_used` name. This is the boundary the
  route uses — it holds no live `Source` object, but the *source* still owns the
  normalization, so Slice 5's creator sources plug in identically. This replaces
  the original plan's "read `candidate.raw` directly" simplification, which
  correction #3 explicitly rejected.

Because grounding (§4.2) checks citations against this normalized shape, stored
citations read uniformly across providers (e.g. `employees: 180`), regardless of
whether Apollo or seed produced the row.

### 4.2 Batch scoring + grounding

```python
class ScoreStatus(str, Enum):
    LLM_OK = "llm_ok"                    # batch scored by the LLM, all grounded
    PARTIAL_HEURISTIC = "partial_heuristic"  # LLM scored, but ≥1 target fell back
    NO_GEMINI_KEY = "no_gemini_key"      # no key anywhere → all heuristic
    INVALID_GEMINI_KEY = "invalid_gemini_key"  # credential rejected → all heuristic
    GEMINI_ERROR = "gemini_error"        # other Gemini failure → all heuristic


@dataclass
class TargetScore:
    fit_score: int
    reasons: list[FitReason]
    scored_by: str  # "llm" or "heuristic"


@dataclass
class ScoreOutcome:
    scores: list[TargetScore]  # aligned 1:1 with the input evidence list
    status: ScoreStatus
    llm_scored: int
    heuristic_scored: int
    reason: str | None  # sanitized, safe for UI/audit; None unless a failure occurred


def score_batch(
    brief: Brief, evidence_list: list[dict], settings: dict[str, str]
) -> ScoreOutcome: ...
```

Flow inside `score_batch` (correction #4 — honest aggregation; correction #5 —
one call):

1. If `evidence_list` is empty, return an empty `ScoreOutcome` (the route's
   zero-target branch in §6 means this is normally never reached, but it is
   safe).
2. Build one prompt from the brief plus every target's normalized evidence,
   each tagged with its `target_index`, and ask for a `FitBatch`.
3. `result = llm.generate_structured(FitBatch, SYSTEM_PROMPT, prompt, settings)`:
   - `None` (no key anywhere) → every target scored by `_heuristic(...)`;
     `status = NO_GEMINI_KEY`, `reason = None`.
   - raises `LLMError(INVALID_KEY)` → every target heuristic;
     `status = INVALID_GEMINI_KEY`, `reason = exc.message`. **This is a single
     403 on the one batch call — there is no per-target loop to keep hitting, so
     "stop after a terminal credential failure" is satisfied by construction.**
   - raises `LLMError(ERROR)` → every target heuristic; `status = GEMINI_ERROR`,
     `reason = exc.message`.
   - returns a validated `FitBatch` → step 4.
4. For each target index `i`: take the assessment whose `target_index == i` (if
   the model omitted it, duplicated it, or returned an out-of-range index, treat
   it as missing). **Verify grounding**: every `FitReason` must satisfy
   `_is_grounded(reason, evidence_list[i])`. A missing assessment, or one with
   any ungrounded reason, is discarded and that single target is scored by
   `_heuristic(brief, evidence_list[i])` (which is grounded by construction).
   Count LLM-scored vs heuristic-scored targets honestly.
5. Aggregate status: all-LLM-and-grounded → `LLM_OK`; LLM batch succeeded but
   ≥1 target fell back → `PARTIAL_HEURISTIC` (with `reason` naming the count).

`_is_grounded(reason, evidence)` returns `True` iff **all** of:
1. `reason.evidence_key` is a key in `evidence`;
2. the stored value `evidence[reason.evidence_key]` is **not `None` and not
   blank** — a key that exists but carries no value (e.g. `country: None`, or an
   empty/whitespace string) can never ground a citation;
3. `_norm(evidence[reason.evidence_key]) == _norm(reason.evidence_value)`, where
   `_norm` lowercases, strips, and compares integers by their string form.

A fabricated field, a citation of an empty/`None` evidence field, or a misquoted
value all fail — this is what makes citations grounded rather than merely
non-empty. (Rule 2 matters because a normalized-evidence field is often `None`
for these sources — `industry`/`employees`/`country` are all optional in §4.1 —
so "the key exists" is not enough on its own.)

The four-way LLM status split (NO_KEY / INVALID_KEY / other-error / OK) reuses
the correction-3 discipline established for intake in Slice 2: a rejected
credential is never conflated with a network/parse error. `PARTIAL_HEURISTIC` is
the one new state — it exists specifically so the batch outcome is reported
honestly (correction #4) rather than assumed uniform.

### 4.3 Deterministic heuristic (correction #7 — exact spec)

`_heuristic(brief, evidence) -> tuple[int, list[FitReason]]` is a pure function
of the normalized evidence, so it is stable, testable, and always grounded.
Three additive components, max 100:

**Tokenization** (`_tokens(text)`): lowercase, split on non-alphanumeric, drop
the stopword set `{"and", "&", "the", "of", "for", "a", "an", "to", "in", "or"}`,
drop empties. Domain words like "distribution"/"logistics" are **not**
stopwords.

| Component | Points | Rule | Missing-field behavior |
|---|---|---|---|
| Industry overlap | 0–60 | `i = |_tokens(evidence.industry) ∩ _tokens(brief.niche_or_industry)|`; component `= round(60 * i / max(1, len(_tokens(brief.niche_or_industry))))` | `industry is None` → 0 points, **no reason emitted** (can't cite a value that isn't there) |
| Size band | 0–25 | `100–600 → 25`; `50–99 or 601–1000 → 15`; `1–49 or >1000 → 5` | `employees is None` → 0 points, no reason emitted |
| Country match | 0–15 | `evidence.country in brief.target_countries → 15` else `0` | `country is None` → 0 points, no reason emitted |

Each component that *can* be computed emits exactly one grounded `FitReason`
citing the field it used (`evidence_key`/`evidence_value` taken verbatim from the
evidence, so grounding is guaranteed). If, after all three, no reason was emitted
(all three fields missing — not possible for either current source, but handled),
one fallback reason cites `name`, so the "≥1 reason" invariant always holds. Final
score is the clamped sum, `min(100, max(0, total))`.

**Canonical test brief** (anchors the §11 tests): `product="magnesium
supplements"`, `niche_or_industry="health & wellness distribution"`,
`target_countries=["United States"]`. `_tokens(niche) = {health, wellness,
distribution}` (len 3). Expected heuristic scores against the seed set:

| Seed company | industry ∩ | size band | country | total | band |
|---|---|---|---|---|---|
| Cornerstone Wellness Distributors (75) | 3 → 60 | 75 → 15 | US → 15 | **90** | high |
| Meridian Health Supply (95) | 3 → 60 | 95 → 15 | US → 15 | **90** | high |
| Northbridge Distribution (180) | 1 → 20 | 180 → 25 | US → 15 | **60** | low |
| Cascade Logistics (340) | 0 → 0 | 340 → 25 | US → 15 | **40** | low |
| Ironclad Freight (520) | 0 → 0 | 520 → 25 | US → 15 | **40** | low |
| Summit Supply Chain (410) | 0 → 0 | 410 → 25 | US → 15 | **40** | low |
| **Lakeside Software Studio (12)** — the weak seed | 0 → 0 | 12 → 5 | US → 15 | **20** | low |

This gives a real spread (20 → 90), makes the weak target unambiguously the
lowest and clearly <70, and does it on the pure zero-key demo path. These exact
totals are asserted in the retained tests (§11).

**Known limitation** (stated plainly): the heuristic is a demo-mode stand-in,
not a real fit model. It exists so the zero-key flow completes with honest,
grounded reasoning — the LLM path is the real scorer when a key is present.

---

## 5. Where scoring runs — at discovery time, one batch, one transaction

Correction #5. Extends the Slice 2 `create_campaign` sequence so the detail page
stays a pure read and each target is scored exactly once (the `memory`
non-negotiable — no re-discovery/re-scoring of known targets). The corrected
order in `app/main.py`:

```
1. Parse the Brief (intake), retain IntakeStatus.
2. Create the campaign, obtain campaign_id.
3. Write the intake audit row.
4. Run discovery → SourceResult (candidates, source_used).
5. Write the discovery audit row.
6. ZERO-TARGET BRANCH: if not candidates:                 # NEW, explicit
     - db.add_audit(..., "scoring.skipped_no_targets", detail=None)
     - redirect to /campaigns/{id}   (nothing to score or persist)
7. Build normalized evidence for every candidate through the source boundary:
     evidence_list = [sources.evidence_for(result.source_used, c)
                      for c in candidates]
8. Score the whole batch at once:                         # NEW, one LLM call
     outcome = scoring.score_batch(brief, evidence_list, settings)
9. Persist targets AND their fit in ONE transaction:      # NEW, atomic
     db.add_scored_targets(workspace_id, campaign_id,
                           candidates, result.source_used, outcome.scores)
10. Write ONE scoring audit row from the aggregate outcome (scoring.<status>),
    detail carries the sanitized reason / honest counts.
11. Redirect to /campaigns/{id}.
```

Why this shape satisfies the corrections:

- **Bounded latency (#5):** scoring is a single `generate_structured` call
  (≤2 HTTP calls counting the existing shape-retry), independent of target
  count — not `N × 2 × 30s`. The zero-key path is the instant heuristic (no
  HTTP at all).
- **No partial scoring (#5):** targets and their scores are written together in
  one `add_scored_targets` transaction (§7). A crash mid-slice leaves either a
  fully-scored campaign or no targets at all — never half-scored rows.
- **Zero targets defined (#5):** if discovery yields nothing (e.g. `SEED_ERROR`
  with an empty list), scoring is skipped, an explicit
  `scoring.skipped_no_targets` audit row is written (no banner), and the detail
  page shows its existing "No candidates matched" empty state.
- **Honest status (#4):** the one scoring audit row carries the aggregate
  outcome, including the LLM-vs-heuristic counts, not an assumed-uniform status.

---

## 6. Terminal credential failure (correction #4, restated)

With a single batch call, "stop repeated LLM calls after a terminal credential
failure" is inherent: an invalid Gemini key produces one 403 on the one call,
`llm._call_gemini` raises `LLMError(INVALID_KEY)` before any retry fires, and
`score_batch` scores every target with the heuristic and reports
`INVALID_GEMINI_KEY`. There is no per-target loop that could keep re-hitting a
rejected credential. (Had we chosen concurrent per-target scoring, this rule
would have required explicit early-abort logic; the batch design removes the
hazard entirely — the reason it was chosen in §0.)

---

## 7. DB (`app/db.py`)

One new function, replacing the original plan's separate `update_target_fit`
(correction #5 — persist targets and scores atomically):

```python
def add_scored_targets(
    workspace_id: int, campaign_id: int,
    candidates: list[Candidate], source_name: str,
    scores: list[TargetScore],   # aligned 1:1 with candidates
) -> None:
    # GUARD FIRST, before opening any connection: candidates and scores must be
    # the same length. A zip() over mismatched lists would silently drop the
    # tail — omitting real targets or scores. On a mismatch, raise ValueError
    # and write ZERO rows (fail loudly, never lose a target).
    if len(candidates) != len(scores):
        raise ValueError("candidates and scores must be 1:1")
    # ONE connection, ONE executemany, ONE commit. Each row inserts the target
    # fields AND fit_score + fit_reasons_json together, so a campaign is never
    # left partially scored.
    # fit_reasons_json = json.dumps([r.model_dump() for r in score.reasons])
    # WHERE-clause / INSERT columns all carry workspace_id (Slice 1 isolation).
```

The guard runs *before* the connection is opened, so a length mismatch is a
zero-write error, not a partial insert. `score_batch` already returns `scores`
aligned 1:1 with its input `evidence_list`, and the route builds `evidence_list`
from `candidates` in the same order (§5), so in normal operation the lengths
always match — the guard exists to make a future refactor that breaks that
invariant fail loudly instead of silently truncating via `zip`.

`add_targets` from Slice 2 stays for reference/back-compat but is no longer on
the create-campaign path; if kept, note it in the module. Isolation guarantee is
unchanged: every inserted row carries `workspace_id`, and there is no
cross-campaign or cross-workspace write.

---

## 8. Audit + banner (`app/audit_banners.py`)

Add a third explicit map (no enum-value string interpolation, same discipline as
Slice 2), including the new zero-target and partial-heuristic actions:

```python
SCORING_MAP: dict[ScoreStatus, tuple[str, str | None, str | None]] = {
    ScoreStatus.LLM_OK: ("scoring.llm_ok", None, None),  # silent on success
    ScoreStatus.PARTIAL_HEURISTIC: ("scoring.partial_heuristic", "info",
        "Some targets were scored with the built-in heuristic ({reason})."),
    ScoreStatus.NO_GEMINI_KEY: ("scoring.no_gemini_key", "info",
        "Fit scored with the built-in heuristic (no Gemini key). Paste a Gemini key in Settings for LLM-scored fit."),
    ScoreStatus.INVALID_GEMINI_KEY: ("scoring.invalid_gemini_key", "warning",
        "Gemini rejected the scoring request ({reason}). Scored with the built-in heuristic instead — check your Gemini key in Settings."),
    ScoreStatus.GEMINI_ERROR: ("scoring.gemini_error", "warning",
        "Gemini couldn't complete scoring ({reason}). Scored with the built-in heuristic instead."),
}
# scoring.skipped_no_targets is written directly by the route (no banner);
# it is a neutral audit record, not a status→banner mapping.
```

`BANNER_BY_ACTION` already iterates `[*DISCOVERY_MAP.values(),
*INTAKE_MAP.values()]`; extend it to include `*SCORING_MAP.values()`.
`campaign_detail` already renders `intake.*`/`discovery.*` audit rows as banners;
extend that filter to `scoring.*` so a third banner stacks below the other two
(same `.banners` column, ordered intake → discovery → scoring). Existing
`--info`/`--warning` tokens only — no new colors.

---

## 9. UI (`campaign_detail.html` + `app.css`)

- **Fit column**: add a right-aligned **Fit** column (mono, per design.md's
  numeric-column rule). Column order becomes Company · Domain · Country · Size ·
  **Fit** · Source. The route computes the coloring class so the template stays
  logic-light: `fit--high` (`--success`) ≥85, `fit--mid` (`--text`) 70–84,
  `fit--low` (`--text-3`) <70.
- **Cited reasons on expand (correction #7 — accessible):** the Fit cell holds a
  real caret **button**:
  ```html
  <button class="caret" aria-expanded="false" aria-controls="reasons-{{ t.id }}">
    <span class="visually-hidden">Toggle reasons for {{ t.name }}</span>▸
  </button>
  ```
  Each target row is followed by a hidden reasons row
  `<tr id="reasons-{{ t.id }}" class="reasons-row" hidden>` whose single cell
  spans all columns and lists each `reason` with its `evidence_key:
  evidence_value` citation. A small vanilla-JS handler toggles the row's
  `hidden` attribute and flips `aria-expanded` between `"true"`/`"false"`.
  Because it is a native `<button>`, **Enter/Space and tab-focus work with no
  extra JS**; `:focus-visible` uses `--ring`. This replaces the original plan's
  optional, mouse-only row-click.
- The route parses `fit_reasons_json` into a list of dicts per target and passes
  it to the template.
- CSS (tokens only, no invented colors): `.fit--high/.fit--mid/.fit--low`,
  `.caret` (+ `.caret[aria-expanded="true"]` rotation), `.reasons-row`,
  `.reason`, `.reason__citation`, `.visually-hidden`.

---

## 10. Seed data — add one deliberately weak company (owner-decided)

Append one clearly off-brief entry to `seeds/companies.json` so it scores 20 on
the canonical brief (§4.3), well below 70:

```json
{
  "name": "Lakeside Software Studio",
  "domain": "lakesidesoftware.io",
  "industry": "Consumer mobile apps",
  "employees": 12,
  "city": "Madison",
  "state": "WI",
  "country": "United States"
}
```

This changes the US seed count from 6 to **7** (total seeds 10 → 11; UK/Germany
unchanged at 2 each). **Correction #6:** this breaks the existing Slice 2
assertion `len(targets) == 6` at
[tests/test_slice2_hardening.py:378](tests/test_slice2_hardening.py:378). That
test must be updated in the same slice — rename it to reflect 7 US seeds and,
to avoid re-breaking on future seed edits, assert the count against the number
of US rows read from `seeds/companies.json` rather than a hard-coded literal,
plus assert the weak row is present and (once scored) lands in the `fit--low`
band. The change in count is recorded in PROGRESS.md and the collaboration log
at slice completion.

---

## 11. Files changed / created (implementation phase, not this commit)

**New:**
- `app/agent/scoring.py` (batch scoring, grounding, heuristic).
- `tests/test_slice3_scoring.py` (retained — see the test list in §11.1 below).

**Modified:**
- `app/models.py` — `FitReason`, `FitAssessment`, `FitBatch`.
- `app/sources/apollo.py` — `normalize_evidence` + `evidence()` delegates.
- `app/sources/seed.py` — `normalize_evidence` + `evidence()` delegates.
- `app/sources/__init__.py` — `evidence_for(source_used, candidate)` dispatcher.
- `app/db.py` — `add_scored_targets` (atomic target+fit insert).
- `app/main.py` — scoring step + zero-target branch in `create_campaign`; parse
  reasons + compute fit class in `campaign_detail`; extend the banner filter to
  `scoring.*`.
- `app/audit_banners.py` — `SCORING_MAP` + extend `BANNER_BY_ACTION`.
- `app/templates/campaign_detail.html` — Fit column, accessible caret, reasons
  rows, small JS.
- `app/static/css/app.css` — fit/caret/reasons/visually-hidden classes.
- `seeds/companies.json` — one weak entry.
- **`tests/test_slice2_hardening.py`** — update the now-invalid 6-target
  assertion (correction #6; this file was omitted from the original plan).
- `PROGRESS.md`, `DECISIONS.md`, `collaboration.md` at slice end.

**This revision** touches only `SLICE_3_PLAN.md` (and `collaboration.md` at
commit time).

### 11.1 Retained tests (correction #6 — no throwaway scripts)

A maintained suite now exists (`tests/test_slice2_hardening.py`), so Slice 3 adds
**retained** `unittest` tests, not temporary scripts:

1. **Schema shape:** `FitReason` rejects blank `reason`/`evidence_key`/
   `evidence_value`; `FitAssessment` rejects empty `reasons` and out-of-range
   scores.
2. **Grounding:** `_is_grounded` accepts a citation matching the evidence;
   rejects (a) a missing key, (b) a mismatched value in both integer and string
   forms, and (c) **a key whose evidence value is `None` or a blank/whitespace
   string** (e.g. a `country: None` citation) — the correction that "the key
   exists" is not sufficient.
3. **Heuristic anchors:** the canonical brief (§4.3) reproduces the exact totals
   in the table (weak seed = 20 <70; Cornerstone/Meridian = 90 ≥85); every
   heuristic reason is grounded against its evidence.
4. **Normalization:** an Apollo raw row (`estimated_num_employees`) and a seed
   raw row (`employees`) both normalize to `evidence["employees"]`.
5. **Batch aggregation — ungrounded:** with `llm.generate_structured` mocked to
   return a `FitBatch` where one target's citation is ungrounded, that target is
   heuristic-scored, the rest are LLM-scored, and the outcome counts +
   `PARTIAL_HEURISTIC` status are honest.
6. **Batch aggregation — malformed `target_index`:** three mocked cases proving
   the §4.2 step-4 promise, each falling back only the affected target(s) to the
   heuristic with honest counts:
   - **missing** — the batch omits one target's index entirely;
   - **duplicate** — two assessments claim the same index (the extra is ignored,
     the un-covered index falls back);
   - **out-of-range** — an index `< 0` or `>= len(evidence_list)` is dropped.
7. **Terminal credential failure:** mocked `LLMError(INVALID_KEY)` → all targets
   heuristic, `INVALID_GEMINI_KEY`, and the mock is called exactly once (no
   retry loop).
8. **Atomic persistence + isolation:** `add_scored_targets` writes all rows for
   the given workspace/campaign only; a second workspace sees none; scores read
   back match. **Length-guard:** calling it with `len(candidates) != len(scores)`
   raises `ValueError` and writes **zero** rows (verified by a follow-up count).
9. **Zero targets:** a campaign whose discovery returns no candidates writes no
   target rows and records `scoring.skipped_no_targets`.

All mocked (no real provider calls, no real keys), temp SQLite, no `outpost.db`
writes — same pattern as `test_slice2_hardening.py`.

### 11.2 Manual/computed-style verification (proportional to risk)

After the retained suite is green:

- **No-key path:** one no-key business campaign in a scratch workspace to confirm
  end-to-end that seed targets show heuristic fit with the right coloring, the
  weak row is visibly <70, the caret expands its grounded reasons (and works via
  keyboard), and the `scoring.no_gemini_key` banner + audit row are present.
- **Live Gemini batch (required — mocks can't prove the schema is accepted):**
  one business campaign scored against a **live** Gemini key. The mocked tests
  prove our aggregation logic but *cannot* prove Gemini accepts the new nested
  `FitBatch` `responseJsonSchema` (a list of objects, each with a nested list of
  objects) — only a real call can. Procedure, honoring every key rule from the
  Slice 2 hardening pass:
  - The owner pastes a **freshly rotated** Gemini key through the Settings page
    only; any key posted in chat is treated as compromised and never used.
  - The key is located for verification by workspace / length / timestamp only
    (`SELECT ... length(key_value) ...`), **never by reading its value**.
  - Run one campaign and accept either honest outcome: `scoring.llm_ok` (batch
    accepted and all targets grounded) **or** `scoring.partial_heuristic` (batch
    accepted, some targets fell back) — both prove Gemini accepted the schema. A
    `scoring.gemini_error` mentioning schema/`INVALID_ARGUMENT` means the
    `FitBatch` schema was rejected and must be adjusted before the slice is
    considered done. **Stop and report if that occurs** rather than shipping.
  - Confirm **no credential leakage**: the key never appears in console output,
    audit `detail`, `git diff`, `git log`, or any tracked file (`grep` the
    key-prefix as in Slice 2).
- **Computed-style:** `.fit--high/mid/low` resolve to `--success`/`--text`/
  `--text-3` in both themes.

At most two screenshots for the whole slice, after every check passes. No
`outpost.db` rows deleted or reset; verification adds normal product data only,
as in Slices 1–2.

---

## 12. Decisions to log in DECISIONS.md (at slice completion, not this commit)

- Fit-scoring runs at discovery time and is stored once per target; the detail
  page stays a pure read (memory non-negotiable — no re-scoring known targets).
- Scoring is a **single batch LLM call** returning a `FitBatch`, not a per-target
  loop — bounded latency, honest per-target aggregation, and a credential
  failure that is a single 403 rather than a retry storm.
- Citations are **grounded**: the schema requires an `evidence_key`/
  `evidence_value` pair and a non-empty reason, and `scoring.py` verifies that
  pair against the supplied normalized evidence before any score is stored. A
  fabricated citation is discarded and that target falls back to the heuristic.
- Evidence is normalized at the **`Source.evidence()` boundary**; scoring never
  reads provider-specific keys (Apollo `estimated_num_employees` vs seed
  `employees`), so citations read uniformly across sources.
- Targets and their scores are persisted in **one transaction**
  (`add_scored_targets`); a campaign is never left partially scored, and a
  zero-target discovery is an explicit, audited no-op.
- A deterministic heuristic scorer (exact weights in §4.3) keeps the zero-key
  demo path scoring with honest, grounded reasoning; the LLM is the real scorer
  when a key is present.
- `ScoreStatus` distinguishes a rejected credential from every other failure and
  adds `PARTIAL_HEURISTIC` so a mixed batch outcome is reported honestly.
- One deliberately weak seed company was added so the "weak target scores low"
  criterion is demonstrable without a live LLM (US seed count 6 → 7); the Slice 2
  seed-count test was updated to match.
