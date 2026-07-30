# Slice 3 Plan — Fit-scoring with citations

Owner-approved plan for Slice 3 (SPEC.md §6). This document is the single
source of truth for Slice 3's design. No implementation has started as of this
commit — this commit contains only `SLICE_3_PLAN.md` and a `collaboration.md`
log entry.

## 0. Collaboration & model status

- **SDE 1** (this session) created this plan. Two design forks were put to the
  owner and decided before writing it: (1) fit-scoring runs **at discovery
  time**; (2) a **deliberately weak seed company** is added so the no-key demo
  always shows a visible sub-70 score.
- Planning was done on the stronger reasoning model (Opus). Recommended
  **execution model: Sonnet** — this slice is mechanical execution from a
  settled plan. Stated again at the top of implementation so the owner can
  confirm the switch before code begins (CLAUDE.md).
- Per `collaboration.md` rule 6: implementation begins only after the owner
  confirms this plan has no further outstanding changes.
- Non-negotiables in play (CLAUDE.md): #2 demo mode always completes (scoring
  must work with zero keys), #4 every action audited, #5 structured output
  validated with retry, #6 workspace isolation, plus the `Local data` rule
  (no reset/delete of `outpost.db` or seeds) and the `Collaboration` rule.

---

## 1. Goal and done-when (SPEC.md §6)

For each discovered target, pull evidence and score fit 0–100 with reasons
that cite specific evidence. Structured output validated, retry on bad parse,
**no score without at least one citation**. Fit coloring per design.md (≥85
`success`, 70–84 `text`, <70 `text-3`).

**Done when:** the discovery table shows a fit score and, on expand, cited
reasons for each target, and a deliberately weak target scores low with honest
reasons.

---

## 2. What already exists (reused unchanged)

- `target` table already carries `fit_score INTEGER` and
  `fit_reasons_json TEXT` (added in Slice 2's schema for exactly this slice) —
  **no migration needed**.
- `Source.evidence(candidate) -> dict` is defined on the interface and returns
  `candidate.raw` for both `ApolloSource` and `SeedSource`.
- `llm.generate_structured(schema, system, user, settings)` already does the
  two-shot, schema-aware retry and raises `LLMError(kind=...)` distinguishing a
  rejected credential (`INVALID_KEY`) from every other failure (`ERROR`), or
  returns `None` when no key is configured anywhere.
- `campaign_detail` is a pure read that re-derives banners from the audit trail
  via `audit_banners.banner_for(...)`. Slice 3 keeps it a pure read.
- `audit_banners.BANNER_BY_ACTION` is derived by iterating the status maps, so
  adding a third map wires banners automatically.

---

## 3. Structured-output schema (`app/models.py`)

```python
from pydantic import BaseModel, field_validator, model_validator

class FitReason(BaseModel):
    reason: str
    citation: str  # points at specific evidence, e.g. "estimated_num_employees: 180"

    @field_validator("citation")
    @classmethod
    def citation_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("every reason must cite specific evidence")
        return v

class FitAssessment(BaseModel):
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
```

"No score without at least one citation" is enforced by the schema itself:
each `FitReason` requires a non-empty `citation`, and `FitAssessment` requires
`len(reasons) >= 1`. A model response that returns a bare score with no
reasons, or a reason with an empty citation, fails validation → the existing
two-shot retry fires → a second failure raises `LLMError(kind=ERROR)` → the
caller falls back to the heuristic (§4), which always cites. There is no code
path that stores a score with zero citations.

---

## 4. Scoring module (`app/agent/scoring.py`)

Mirrors `intake.py`'s status-carrying shape so the route can audit the outcome
uniformly.

```python
class ScoreStatus(str, Enum):
    LLM_OK = "llm_ok"
    NO_GEMINI_KEY = "no_gemini_key"
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"

@dataclass
class ScoreResult:
    assessment: FitAssessment
    status: ScoreStatus
    reason: str | None   # sanitized, safe for UI/audit; None on LLM_OK/NO_GEMINI_KEY

def score_target(brief: Brief, evidence: dict, settings: dict[str, str]) -> ScoreResult: ...
```

- Builds a prompt from the brief (product, audience, niche_or_industry, target
  countries) plus the `evidence` blob as compact JSON, and asks for a 0–100 fit
  with reasons that each quote a specific evidence field.
- `llm.generate_structured(FitAssessment, SYSTEM_PROMPT, prompt, settings)`:
  - returns a validated `FitAssessment` → `ScoreResult(..., LLM_OK, None)`.
  - returns `None` (no key anywhere) → heuristic, `NO_GEMINI_KEY`, `None`.
  - raises `LLMError` → heuristic; status is `INVALID_GEMINI_KEY` when
    `exc.kind == INVALID_KEY`, else `GEMINI_ERROR`; `reason = exc.message`.
- The same four-way status split as intake (correction-3 discipline from Slice
  2): a rejected credential is never conflated with a network/parse error.

### 4.1 Deterministic heuristic (demo-mode / no-key path)

`_heuristic_assessment(brief, evidence) -> FitAssessment` scores from evidence
signals and cites the exact field it used, so the zero-key path also satisfies
"no score without a citation." Signals and contribution:

- **Industry / keyword overlap** between `evidence["industry"]` (and name) and
  the brief's `niche_or_industry` / product words — the dominant signal.
- **Size band** from `evidence["employees"]` — mid-size distributors/logistics
  (roughly 100–600) score best; very small or missing scores lower.
- **Country match** to `brief.target_countries`.

The scorer is a pure function of the evidence, so it is stable and testable,
and it produces a spread rather than a constant. Each contributing signal emits
one `FitReason` citing the field (e.g. `citation="industry: Retail software"`,
`reason="Industry doesn't match a distribution/logistics brief"`). A clearly
off-brief target (unrelated industry, tiny size) lands below 70; this is what
the weak seed row in §7 exercises.

**Known limitation** (stated plainly): the heuristic is a demo-mode stand-in,
not a real fit model. It exists so the zero-key flow completes with honest,
cited reasoning — the LLM path is the real scorer when a key is present.

---

## 5. Evidence sourcing — one documented simplification

`score_target` takes an `evidence: dict`. The route obtains it as
`candidate.raw`, which is **exactly what `Source.evidence()` returns for both
current sources** — so this is behaviorally identical to calling
`source.evidence(candidate)` today, while keeping the route from having to hold
a live `Source` object past `discover()`. A code comment records that Slice 5
routes scoring through `source.evidence()` if creator evidence ever diverges
from `raw`. Flagged here as a conscious choice, not a silent bypass of the
source-agnostic interface.

---

## 6. Where scoring runs — at discovery time (owner-decided)

Extends the Slice 2 seven-step `create_campaign` sequence with scoring, so the
detail page stays a pure read and each target is scored exactly once (the
`memory` non-negotiable — no re-discovery/re-scoring of known targets). The
corrected order:

```
1. Parse the Brief (intake), retain IntakeStatus.
2. Create the campaign, obtain campaign_id.
3. Write the intake audit row.
4. Run discovery.
5. Write the discovery audit row.
6. Save the returned targets (db.add_targets).           # unchanged from Slice 2
7. Score every saved target and persist fit:             # NEW
     for target in db.list_targets(workspace_id, campaign_id):
         evidence = json.loads(target["raw_json"] or "{}")
         result = scoring.score_target(brief, evidence, settings)
         db.update_target_fit(workspace_id, target["id"],
                              result.assessment.fit_score,
                              json.dumps([r.model_dump() for r in result.assessment.reasons]))
     # all targets share one settings dict, so the batch status is uniform;
     # record the first non-OK status seen (else LLM_OK) as the campaign's
     # scoring status.
8. Write ONE scoring audit row (scoring.<status>).       # NEW
9. Redirect to /campaigns/{id}.
```

**Latency is bounded and acceptable for this slice:** with a free-plan Apollo
key discovery falls back to ≤10 seed rows, and the zero-key demo path uses the
instant heuristic (no HTTP at all). The only slow case is a paid Apollo plan
(up to 25 rows) *and* a live Gemini key — sequential scoring there is a known
cost/latency cost that Slice 6's routing and early-exit are designed to
address; it is explicitly out of scope here. Noted, not silently accepted.

Scoring runs on `list_targets` output (after step 6) rather than on the raw
candidate list, so `target["id"]` is available for `update_target_fit` and the
stored `raw_json` is the single evidence source — no second in-memory copy to
keep in sync.

---

## 7. Seed data — add one deliberately weak company (owner-decided)

Append one clearly off-brief entry to `seeds/companies.json` — an unrelated
industry and small size so it scores below 70 with honest, cited heuristic
reasons — e.g.:

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

This makes the "deliberately weak target scores low" done-when provable in the
**no-key demo path**, not just with a live LLM. It changes the US seed count
from 6 to **7** (total seeds 10 → 11; UK/Germany counts unchanged at 2 each).
The Slice 2 verification expectation of "6 US seed rows" is superseded for
US-only briefs going forward; recorded in PROGRESS.md and the collaboration log
at slice completion so the change in count is traceable.

---

## 8. Audit + banner (`app/audit_banners.py`)

Add a third explicit map (no enum-value string interpolation, same discipline
as Slice 2):

```python
SCORING_MAP: dict[ScoreStatus, tuple[str, str | None, str | None]] = {
    ScoreStatus.LLM_OK: ("scoring.llm_ok", None, None),  # silent on success
    ScoreStatus.NO_GEMINI_KEY: ("scoring.no_gemini_key", "info",
        "Fit scored with the built-in heuristic (no Gemini key). Paste a Gemini key in Settings for LLM-scored fit."),
    ScoreStatus.INVALID_GEMINI_KEY: ("scoring.invalid_gemini_key", "warning",
        "Gemini rejected the scoring request ({reason}). Scored with the built-in heuristic instead — check your Gemini key in Settings."),
    ScoreStatus.GEMINI_ERROR: ("scoring.gemini_error", "warning",
        "Gemini couldn't complete scoring ({reason}). Scored with the built-in heuristic instead."),
}
```

`BANNER_BY_ACTION` already iterates `[*DISCOVERY_MAP.values(), *INTAKE_MAP.values()]`;
extend it to include `*SCORING_MAP.values()`. `campaign_detail` already renders
`intake.*` and `discovery.*` audit rows as banners; extend that filter to
`scoring.*` so a third banner stacks below the other two (same `.banners`
column, ordered intake → discovery → scoring, matching route order). Existing
`--info`/`--warning` tokens only — no new colors.

---

## 9. DB (`app/db.py`)

One new function, `workspace_id`-required like every other tenant-data call:

```python
def update_target_fit(workspace_id: int, target_id: int,
                      fit_score: int, fit_reasons_json: str) -> None:
    # UPDATE target SET fit_score=?, fit_reasons_json=?
    # WHERE workspace_id=? AND id=?   (both in the WHERE clause)
```

Scoping the write by `workspace_id` in the `WHERE` clause keeps the Slice 1
isolation guarantee: a stray `target_id` from another workspace updates nothing.

---

## 10. UI (`campaign_detail.html` + `app.css`)

- **Fit column**: add a right-aligned **Fit** column (mono, per design.md's
  numeric-column rule). Column order becomes Company · Domain · Country · Size ·
  **Fit** · Source. The score cell gets a coloring class:
  - `fit--high` (`--success`) for ≥85,
  - `fit--mid` (`--text`) for 70–84,
  - `fit--low` (`--text-3`) for <70.
  The route computes the class so the template stays logic-light.
- **Cited reasons on expand**: each target row is followed by a hidden reasons
  row (`<tr class="reasons-row">` with a single cell spanning all columns,
  listing each `reason` and its `citation`). A small vanilla-JS toggle on the
  row (or a caret button in the Fit cell) shows/hides its reasons row —
  consistent with the "light vanilla JavaScript" stack rule and the existing
  row-click pattern in `campaigns_list.html`. The route parses
  `fit_reasons_json` into a list of dicts per target and passes it to the
  template.
- CSS: `.fit--high/.fit--mid/.fit--low`, `.reasons-row`, `.reason`,
  `.reason__citation` — **tokens only**, no invented colors.

---

## 11. Verification (proportional to risk, §14-style)

1. **No-key workspace**: a business campaign's seed targets all receive a
   heuristic fit score; coloring resolves to the right token per band; the weak
   seed row scores <70; expanding a row shows reasons each with a citation;
   `scoring.no_gemini_key` info banner + one audit row present.
2. **"No score without a citation"** — a temporary, DB-write-free script
   constructs a `FitAssessment` with empty `reasons` (and one with an
   empty-citation reason) and confirms both raise `ValidationError`; and that a
   model returning such a shape drives the retry/fallback rather than storing an
   uncited score. Deleted before the slice commit unless kept as a test.
3. **Invalid Gemini key**: via the same temporary script (never UI-pasted fake
   keys), confirm scoring maps to `INVALID_GEMINI_KEY`, all targets still get a
   heuristic score, and the warning banner renders.
4. **Isolation**: fit scores and reasons stay scoped to their workspace and
   campaign (direct `outpost.db` query; Alpha/Beta remain untouched).
5. **Computed-style** checks that `.fit--high/mid/low` resolve to
   `--success`/`--text`/`--text-3` in both themes. At most two screenshots for
   the whole slice, after every check above passes.

No `outpost.db` rows deleted or reset; verification adds normal product data
only, as in Slices 1–2.

---

## 12. Files changed / created (implementation phase, not this commit)

**New:** `app/agent/scoring.py`; a temporary `scripts/verify_fit_paths.py`
(deleted before the final commit unless deliberately kept as a maintained
test).
**Modified:** `app/models.py` (FitReason, FitAssessment), `app/db.py`
(`update_target_fit`), `app/main.py` (scoring step in `create_campaign`; parse
reasons + compute fit class in `campaign_detail`; extend the banner filter to
`scoring.*`), `app/audit_banners.py` (`SCORING_MAP` + `BANNER_BY_ACTION`),
`app/templates/campaign_detail.html` (Fit column + reasons rows + small JS),
`app/static/css/app.css` (fit + reasons classes), `seeds/companies.json` (one
weak entry), plus `PROGRESS.md`, `DECISIONS.md`, `collaboration.md` at slice
end.

**This commit** touches only `SLICE_3_PLAN.md` and `collaboration.md`.

---

## 13. Decisions to log in DECISIONS.md (at slice completion, not this commit)

- Fit-scoring runs at discovery time and is stored once per target; the detail
  page stays a pure read (memory non-negotiable — no re-scoring known targets).
- The citation requirement is enforced by the Pydantic schema, not by route
  logic — there is no code path that stores a score with zero citations.
- A deterministic heuristic scorer keeps the zero-key demo path scoring with
  honest, cited reasoning; the LLM is the real scorer when a key is present.
- `ScoreStatus` distinguishes a rejected credential from every other failure,
  reusing the four-way split established for intake in Slice 2.
- One deliberately weak seed company was added so the "weak target scores low"
  criterion is demonstrable without a live LLM (US seed count 6 → 7).
