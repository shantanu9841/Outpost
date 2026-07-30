# Slice 2 Plan — B2B discovery via Apollo

Owner-approved plan for Slice 2 (SPEC.md §6). This document is the single
source of truth for Slice 2's design; it supersedes any local, uncommitted, or
partial plan draft. No implementation has started as of this commit.

## 0. Collaboration status

- **SDE 1** (this session) created the initial Slice 2 plan, then corrected it
  in full against twelve owner-specified corrections in this same pass.
- **SDE 2** reviewed the initial plan and proposed corrections; **the owner
  approved those corrections**, which are incorporated below.
- **No implementation has started.** This commit contains only
  `SLICE_2_PLAN.md` and a `collaboration.md` log entry.
- Per `collaboration.md` rule 6: SDE 2 (or SDE 1) may begin implementing only
  after the owner confirms this corrected plan has no further outstanding
  changes.
- Per `collaboration.md` rules 1, 8–9: only one SDE may implement in a working
  tree at a time, and if implementation stops before the slice is complete,
  the implementing SDE must write a full handoff entry in `collaboration.md`
  (current branch and latest commit, current slice and approved plan,
  uncommitted files if any, verification already completed, last known
  working state, remaining work, known risks, exact next action) before
  either SDE may resume.
- A prior partial SDE 2 draft of this file existed, uncommitted, on
  `codex/sde-2-slice-2`. It was not read, used, deleted, or overwritten; it
  was preserved via `git stash` on that branch before this document was
  written, per `collaboration.md` rule 10 ("never delete, reset, overwrite,
  or absorb another SDE's uncommitted work without the owner's approval").

---

## 1. Context

Slice 2 v1 (an earlier, uncorrected attempt) built a working end-to-end
business-campaign flow — intake → Source interface → Apollo REST or seed →
discovery table — and was verified in demo mode. Live-Apollo verification
against the owner's real key exposed three real gaps:

1. **Apollo free-tier reality.** Empirically confirmed against the owner's own
   key: `mixed_companies/search`, `mixed_people/search`, and `people/match`
   all return `403 "not included in your Free plan"`. Only
   `organizations/enrich` (single company by known domain) works on free. A
   working free-tier key still cannot discover companies, and the app must
   treat a `403` as a normal, handled outcome — not an error page.
2. **v1's error path was crude.** A 403 rendered the campaign-detail page with
   a raw query-string message, no targets, and no fallback data. Every
   fallback and failure case needs a UI banner and an audit-trail row —
   never a crash, never a silent fallback.
3. **The workspace setting was named `llm` but the code only calls Gemini.**
   Misleading; rename to `gemini` with a data-preserving migration.

Most of v1's work is structurally sound and is reused with the adaptations in
§15. v1 lives on the `slice-2-scratch` branch at commit `96a01f8`.

Non-negotiables in play (CLAUDE.md): #1 BYO-key, #2 demo mode always
completes, #3 source-agnostic, #4 every action audited, #5 structured output
with retry, #6 workspace isolation, plus the `Local data` rule (migrations
must preserve existing `outpost.db` rows) and the `Collaboration` rule.

---

## 2. The Source interface and shared result contract

Every source implements the same two-method interface, and **every source's
`search()` returns the same result type** — there is exactly one contract,
used uniformly, not `list[Candidate]` in one place and a result object
elsewhere.

`app/sources/base.py`:

```python
class SourceStatus(str, Enum):
    OK = "ok"
    NO_KEY = "no_key"
    INVALID_KEY = "invalid_key"
    INSUFFICIENT_PLAN = "insufficient_plan"
    NETWORK_ERROR = "network_error"

@dataclass
class SourceResult:
    candidates: list[Candidate]
    status: SourceStatus
    source_attempted: str   # the source discovery meant to use, e.g. "apollo"
    source_used: str        # the source that actually produced these candidates
    reason: str | None      # human-readable, sanitized, safe for UI/audit

class Source(ABC):
    name: str

    @abstractmethod
    def search(self, brief: Brief) -> SourceResult: ...

    @abstractmethod
    def evidence(self, candidate: Candidate) -> dict: ...
```

`evidence()` intentionally keeps returning a plain `dict`, not a `SourceResult`
— it operates on one already-known candidate and isn't part of the
whole-request fallback/failure surface this slice defines. Only `search()`
needs the shared contract.

`Candidate` (Pydantic, `app/models.py`) is the normalized shape every source
returns inside `SourceResult.candidates`:
`source, external_id, name, handle_or_domain, reach, location, raw`.

**Instantiation per workspace** happens in `sources.get_source`/`discover` in
`app/sources/__init__.py`, using the `{key_name: key_value}` dict
`db.get_settings(workspace_id)` returns. Source objects hold only the API key
string they need, never a `workspace_id` — tenant isolation stays localized to
the routes/db layer (Slice 1's isolation pattern).

`SeedSource.search()` **always returns `SourceResult(status=OK, ...)`** from
its own point of view — reading a bundled JSON file does not fail in this
slice. The "why did we end up on seed data" status (`NO_KEY`,
`INVALID_KEY`, etc.) is not something `SeedSource` knows; it is attached by
`discover()`, which is the only place that understands *why* a fallback
happened. See §5.

---

## 3. Intake — parse "what are you promoting" into a validated Brief

`app/models.py`:

```python
TargetType = Literal["creator", "business"]  # module-level, exported

class Brief(BaseModel):
    product: str
    audience: str
    tone: str
    target_type: TargetType
    niche_or_industry: str
    target_countries: list[str] = Field(default_factory=lambda: ["United States"])
```

`app/agent/intake.py`:

```python
class IntakeStatus(str, Enum):
    LLM_OK = "llm_ok"
    NO_GEMINI_KEY = "no_gemini_key"
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"

@dataclass
class IntakeResult:
    brief: Brief
    status: IntakeStatus
    reason: str | None   # sanitized, safe for UI/audit; None on LLM_OK/NO_GEMINI_KEY

def parse_brief(promoting_what: str, target_type: TargetType,
                 settings: dict[str, str]) -> IntakeResult: ...
```

`target_type` uses the **same `TargetType` Literal** in both `Brief` and this
function's signature — chosen on the intake form, never inferred, because
discovery routing depends on it being reliable.

**Status semantics (correction 3 — this is the load-bearing distinction):**

- `LLM_OK` — Gemini call succeeded, structured output validated.
- `NO_GEMINI_KEY` — no Gemini key anywhere (workspace or free tier); no call
  attempted. Heuristic fallback used.
- `INVALID_GEMINI_KEY` — **only** for a rejected credential: Gemini's API
  returned a response identifiable as an auth rejection (see mapping below).
  Heuristic fallback used.
- `GEMINI_ERROR` — everything else that isn't a credential rejection: network
  failure, timeout, HTTP 5xx, or the schema-validation retry (§7) exhausted
  without success. Heuristic fallback used. **This case did not exist in v1**
  and previously would have been miscategorized as an invalid key.

`app/llm.py` distinguishes these via `LLMError`:

```python
class LLMErrorKind(str, Enum):
    INVALID_KEY = "invalid_key"
    ERROR = "error"

class LLMError(RuntimeError):
    def __init__(self, kind: LLMErrorKind, message: str):
        self.kind = kind
        self.message = message
```

`generate_structured` raises `LLMError(kind=INVALID_KEY, ...)` only when
Gemini's response is recognizable as a credential rejection — HTTP 400 with
`error.status == "INVALID_ARGUMENT"` and a message containing "API key"
(case-insensitive), or HTTP 403. Every other failure — network error,
timeout, other HTTP status, or exhausted retry — raises
`LLMError(kind=ERROR, ...)`. **This exact mapping is unverified against the
live API and must be confirmed by the verification script in §14** before
implementation relies on it; if Gemini's actual error shape differs, the
script's printed output will show it and the mapping gets corrected before
route wiring, not after.

`intake.py` wraps the call:

```python
def parse_brief(promoting_what, target_type, settings) -> IntakeResult:
    try:
        parsed = llm.generate_structured(_ParsedFields, SYSTEM_PROMPT, promoting_what, settings)
    except llm.LLMError as exc:
        status = (IntakeStatus.INVALID_GEMINI_KEY if exc.kind == llm.LLMErrorKind.INVALID_KEY
                  else IntakeStatus.GEMINI_ERROR)
        return IntakeResult(_heuristic_brief(promoting_what, target_type), status, exc.message)
    if parsed is None:
        return IntakeResult(_heuristic_brief(promoting_what, target_type), IntakeStatus.NO_GEMINI_KEY, None)
    brief = Brief(product=parsed.product, audience=parsed.audience, tone=parsed.tone,
                  target_type=target_type, niche_or_industry=parsed.niche_or_industry,
                  target_countries=parsed.target_countries or ["United States"])
    return IntakeResult(brief, IntakeStatus.LLM_OK, None)
```

### 3.1 Zero-Gemini country extraction (correction 4)

`_heuristic_brief` must recognize demo-relevant country names/aliases and
return **all** it finds, defaulting to `["United States"]` only when none are
mentioned — required so the no-Gemini UK/Germany verification (§14) can pass.

```python
_COUNTRY_ALIASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(united states|usa|u\.s\.a\.|u\.s\.|us)\b", re.IGNORECASE), "United States"),
    (re.compile(r"\b(united kingdom|uk|u\.k\.|britain)\b", re.IGNORECASE), "United Kingdom"),
    (re.compile(r"\b(germany|de)\b", re.IGNORECASE), "Germany"),
]

def _extract_countries(text: str) -> list[str]:
    found = []
    for pattern, canonical in _COUNTRY_ALIASES:
        if pattern.search(text) and canonical not in found:
            found.append(canonical)
    return found or ["United States"]
```

Word-boundary matching (`\b`) is required so "DE" only matches the standalone
token, not the middle of "distributor," and "US" doesn't match inside other
words. **Known limitation**, stated plainly: a two-letter code like "DE" is an
inherent ambiguity magnet (e.g. the abbreviation for Delaware); this is a
demo-mode heuristic, not an NLP system, and the limitation is acceptable here.

---

## 4. Apollo source (`app/sources/apollo.py`)

`ApolloSource(Source)`, `name = "apollo"`, constructed with the workspace's
Apollo key string (never a `workspace_id`).

- `search(brief)` posts to
  `https://api.apollo.io/api/v1/mixed_companies/search` with header
  `X-Api-Key: <key>`, body `q_organization_keyword_tags` (from
  `niche_or_industry` + `["distributor", "logistics"]`),
  `organization_locations` (from `target_countries`), `page: 1`,
  `per_page: 25`. Maps `organizations[]` → `Candidate` (id, name,
  `primary_domain`/`website_url`, `estimated_num_employees`, joined
  city/state/country) — this mapping is unchanged from v1 and was confirmed
  live.
- **Never raises.** Returns `SourceResult` directly:
  - 200 → `SourceResult(candidates=[...], status=OK, source_attempted="apollo", source_used="apollo", reason=None)`.
  - 401 → `status=INVALID_KEY` (bad/unrecognized credential).
  - 403 → `status=INSUFFICIENT_PLAN` (a real key, plan doesn't include the
    endpoint — this is Apollo's own documented signature and was confirmed
    live against the owner's key). **Known limitation**: this 401-vs-403
    heuristic is Apollo's convention, not a guarantee; if Apollo ever returns
    403 for a bad key, it would misclassify as insufficient-plan. Acceptable
    given this is BYO-key demo software, not a payments system.
  - `httpx.RequestError` → `status=NETWORK_ERROR`.
  - Any other non-200 → `status=INVALID_KEY` with the sanitized body as
    `reason`.
- All failure branches return `candidates=[]`; `discover()` is responsible for
  substituting seed candidates (§5).
- `evidence(candidate)` returns `candidate.raw` (Slice 3 will enrich).

### 4.1 Sanitizing `reason` (correction 2)

`reason` must never contain API keys, request headers, query strings, URLs, or
raw provider payloads. A helper `_safe_reason(response) -> str`:

1. Try `response.json()["error"]` (Apollo's documented error shape puts the
   human-readable message there) — return it, truncated to 300 characters.
2. If the body isn't parseable JSON or lacks an `error` key, return
   `f"Apollo returned HTTP {response.status_code}"` — never the raw body.
3. Never include `response.request.headers`, `response.request.url`, or the
   request body in any returned string.

`add_audit` (§6) applies a second, defensive truncation (500 chars) on
`detail` as a belt-and-braces measure, independent of source-level
sanitization.

---

## 5. Fallback semantics (correction 2 — exact behavior)

`app/sources/__init__.py`:

```python
def discover(brief: Brief, settings: dict[str, str]) -> SourceResult:
    if brief.target_type != "business":
        # Creator sources arrive in Slice 5.
        seed = SeedSource("creator").search(brief)
        return SourceResult(seed.candidates, SourceStatus.NO_KEY,
                             source_attempted="youtube", source_used="seed",
                             reason="Creator sources arrive in Slice 5")

    apollo_key = settings.get("apollo")
    if not apollo_key:
        seed = SeedSource("business").search(brief)
        return SourceResult(seed.candidates, SourceStatus.NO_KEY,
                             source_attempted="apollo", source_used="seed", reason=None)

    apollo_result = ApolloSource(apollo_key).search(brief)
    if apollo_result.status == SourceStatus.OK:
        return apollo_result  # source_attempted == source_used == "apollo"

    # Apollo failed without raising; fall back to seed, but preserve why.
    seed = SeedSource("business").search(brief)
    return SourceResult(seed.candidates, apollo_result.status,
                         source_attempted="apollo", source_used="seed",
                         reason=apollo_result.reason)
```

Exactly as specified:

- **Successful Apollo:** `source_attempted="apollo"`, `source_used="apollo"`, `status=OK`.
- **No Apollo key:** seed candidates, `source_attempted="apollo"`,
  `source_used="seed"`, `status=NO_KEY`.
- **Invalid key / insufficient plan / network error:** `ApolloSource` returns
  the typed failure without raising; `discover()` runs `SeedSource` and
  returns seed candidates while **preserving the original Apollo failure
  status and sanitized reason**.
- The UI therefore always shows both the fallback data and why fallback
  occurred (§8).

**Rejected:** silently returning seed data with no indication of why
(violates "never a silent fallback"). **Rejected:** raising/crashing on
`INSUFFICIENT_PLAN` (v1's behavior — the key is valid, only plan-limited).

**Known, accepted imprecision:** the creator branch (target_type != business)
reuses `SourceStatus.NO_KEY`, which `DISCOVERY_MAP` (§8) renders as
`discovery.no_apollo_key` — not strictly accurate for a creator campaign. This
is acceptable because the branch is unreachable through the shipped UI this
slice: the intake form's creator radio input is `disabled` (§10), and a
disabled input is excluded from form submission by the HTML spec, so
`target_type="creator"` can only reach this route via a deliberately crafted
raw request, not through the product surface. It exists purely so that edge
case degrades gracefully (seed data, a slightly imprecise banner) rather than
crashing. Slice 5 introduces real creator-source statuses and retires this
placeholder.

---

## 6. Rename setting `llm` → `gemini` (with migration)

Unchanged from the prior plan:

- `db.py`: `SETTING_KEYS = ("youtube", "apify", "apollo", "gemini")`.
- `init()` runs, after table creation, an idempotent migration:
  `UPDATE workspace_setting SET key_name = 'gemini' WHERE key_name = 'llm'`.
  Safe on every startup; preserves existing rows (CLAUDE.md `Local data`).
- `settings.html`: label → "Gemini (LLM)", field `name="llm"` → `name="gemini"`.
- `main.py` `save_settings`: param `llm` → `gemini`.
- `app/llm.py` `_resolve_key`: `settings.get("gemini")` first, then
  `os.environ.get("GEMINI_API_KEY")`.

---

## 7. Structured-output retry

`llm.generate_structured(schema, system, user, settings)`:

1. **First call**: system prompt + a JSON-schema block
   (`schema.model_json_schema()`, compact JSON) + user text. Ask for JSON
   matching that schema.
2. On `ValidationError` or `JSONDecodeError`: **second call**, not a repeat —
   its message includes the original user text, the model's own bad output,
   and `f"Your previous response failed validation: {error}. Return only
   JSON matching the schema above."` The model sees its own mistake and the
   validator's complaint.
3. Second failure → raise `LLMError(kind=ERROR, ...)` (this is one of the
   `GEMINI_ERROR` triggers, §3).

`generate_structured` returns `BaseModel | None` — `None` only for "no key
configured anywhere" (`NO_GEMINI_KEY` upstream); raises `LLMError` for every
other failure mode, letting `intake.py` distinguish `INVALID_GEMINI_KEY` from
`GEMINI_ERROR` by `exc.kind`.

---

## 8. Explicit status → audit action → banner mapping (correction 7)

No status is ever turned into an audit action via string interpolation of the
enum value (`f"discovery.{status.value}"` would incorrectly turn `NO_KEY` into
`discovery.no_key`, not `discovery.no_apollo_key`). Instead, `app/audit_banners.py`
holds explicit, hand-written maps, imported by both `main.py` (real behavior)
and the verification script (§14, so what the script prints is guaranteed to
match production):

```python
DISCOVERY_MAP: dict[SourceStatus, tuple[str, str | None, str | None]] = {
    # status: (audit_action, banner_severity, banner_template)
    SourceStatus.OK: ("discovery.apollo_ok", None, None),  # no banner on success
    SourceStatus.NO_KEY: ("discovery.no_apollo_key", "info",
        "Using seed data (no Apollo key). Paste an Apollo key in Settings to search live companies."),
    SourceStatus.INVALID_KEY: ("discovery.invalid_apollo_key", "warning",
        "Apollo rejected the request ({reason}). Falling back to seed data — check your Apollo key in Settings."),
    SourceStatus.INSUFFICIENT_PLAN: ("discovery.insufficient_plan", "warning",
        "Apollo rejected the request ({reason}). Falling back to seed data — your Apollo plan doesn't include company search."),
    SourceStatus.NETWORK_ERROR: ("discovery.network_error", "warning",
        "Couldn't reach Apollo ({reason}). Falling back to seed data — check your connection and try again."),
}

INTAKE_MAP: dict[IntakeStatus, tuple[str, str | None, str | None]] = {
    IntakeStatus.LLM_OK: ("intake.llm_ok", None, None),
    IntakeStatus.NO_GEMINI_KEY: ("intake.no_gemini_key", "info",
        "Parsed with the built-in heuristic (no Gemini key). Paste a Gemini key in Settings for LLM-parsed briefs."),
    IntakeStatus.INVALID_GEMINI_KEY: ("intake.invalid_gemini_key", "warning",
        "Gemini rejected the request ({reason}). Parsed with the built-in heuristic instead — check your Gemini key in Settings."),
    IntakeStatus.GEMINI_ERROR: ("intake.gemini_error", "warning",
        "Gemini couldn't complete the request ({reason}). Parsed with the built-in heuristic instead."),
}
```

Required discovery actions (all present above):
`discovery.apollo_ok`, `discovery.no_apollo_key`, `discovery.invalid_apollo_key`,
`discovery.insufficient_plan`, `discovery.network_error`.

Required intake actions (all present above):
`intake.llm_ok`, `intake.no_gemini_key`, `intake.invalid_gemini_key`,
`intake.gemini_error`.

`OK`/`LLM_OK` write an audit row (every action is audited, CLAUDE.md
non-negotiable #4) but render **no banner** — success is silent in the UI.

**Two distinct lookup directions are needed, not one.** At write time
(`POST /campaigns`, §13), the route has a live `SourceResult`/`IntakeResult`
and needs only the `action` string to pass to `db.add_audit`; it looks that up
directly from `DISCOVERY_MAP[status]`/`INTAKE_MAP[status]` (as shown in §13's
code). At *read* time (`GET /campaigns/{id}`), the route only has what
`db.list_audit(workspace_id, campaign_id)` returns — persisted `action` and
`detail` strings, not a live result object — so rendering a banner requires
going the other direction: action string → (severity, template). `app/audit_banners.py`
therefore also builds a single reverse index, derived once from the two maps
above (action strings are unique across both, so one dict is enough):

```python
BANNER_BY_ACTION: dict[str, tuple[str, str]] = {
    action: (severity, template)
    for action, severity, template in [*DISCOVERY_MAP.values(), *INTAKE_MAP.values()]
    if severity is not None
}

def banner_for(action: str, detail: str | None) -> tuple[str, str] | None:
    """Return (severity, rendered_text) for a persisted audit row, or None
    (OK/LLM_OK actions aren't in BANNER_BY_ACTION and render nothing)."""
    entry = BANNER_BY_ACTION.get(action)
    if entry is None:
        return None
    severity, template = entry
    return severity, template.format(reason=detail or "")
```

`campaign_detail` calls `banner_for(row["action"], row["detail"])` for the
most recent `intake.*` and `discovery.*` rows it loads via `list_audit`, and
renders whatever isn't `None`, in that order (§9).

---

## 9. Banner layout (correction 8)

When both intake and discovery produce a banner, they render as two ordered,
stacked banners — intake first (it runs first in the route sequence, §13),
then discovery — inside a flex column with an explicit design-token gap:

```css
.banners {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);   /* 16px, design.md spacing scale */
  margin-bottom: var(--space-6);
}
```

Only existing tokens are used — no new colors: `banner--info` uses
`--info`/`--info-subtle`; `banner--warning` uses `--warning`/`--warning-subtle`
(both already defined in `tokens.css`; the classes are new but the colors are
not).

---

## 10. Discovery table UI (design.md §4)

Columns: **Company · Domain · Country · Size · Source**. (v1 additionally
showed Industry and full city/state/country; per the owner's explicit column
list this drops Industry and shows only the country portion of location.
Industry stays in `target.raw_json` for Slice 3's use.)

Style per design.md §4: header row `bg-subtle`, 11px/600 `text-3` uppercase
labels (letter-spacing .05em); 13px cells; 1px `border` row separators;
`surface-hover` on hover; **Size right-aligned in the mono font**. Fit column
deliberately deferred to Slice 3.

All needed CSS classes (`.table`, `.table-wrap`, `.table__num`, `.mono`)
already exist from v1 and need no changes for the table itself — only the
banner classes above are new.

---

## 11. Seed data (`seeds/companies.json`)

10 plausible distributor/logistics companies across 3 countries so the demo
shows filtering: **6 United States, 2 United Kingdom, 2 Germany**. Reuses 8 of
v1's 10 US entries (the two weakest — Blue Anchor Trading Co. and Pinehurst
Retail Partners — are dropped) and adds 4 new international entries.

`SeedSource.search()` filters by `brief.target_countries` when non-empty
(returns only matching-country entries); empty list returns all. This is the
mechanism §3.1's country-extraction heuristic feeds — a no-Gemini brief
mentioning "UK" and "Germany" must extract both, and the seed filter must then
return only the 4 non-US rows.

---

## 12. Data model and audit schema (correction 5 — one final schema)

`app/db.py`, in `init()`:

- `campaign` and `target` tables — unchanged from v1's shape (full column set
  including `fit_*` and `stage` for Slices 3–4, so no future migration needed
  for those).
- **`audit` — the definitive, final schema, including `campaign_id` from the
  start:**

```sql
CREATE TABLE IF NOT EXISTS audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
    campaign_id   INTEGER REFERENCES campaign(id),
    actor         TEXT    NOT NULL,   -- 'agent' this slice, 'human' from Slice 4
    action        TEXT    NOT NULL,
    target_id     INTEGER,            -- null in this slice
    draft_id      INTEGER,            -- null in this slice
    detail        TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

  `campaign_id` is nullable at the schema level (matching `target_id`/
  `draft_id`, for forward compatibility with any future workspace-level audit
  entry not tied to a campaign), but **every audit row Slice 2 writes always
  has a real `campaign_id`**, because the corrected route sequence (§13)
  guarantees `campaign_id` exists before any audit write.
- Migration: `UPDATE workspace_setting SET key_name = 'gemini' WHERE key_name = 'llm'`.

New functions, all **requiring `workspace_id`** (no optional/defaulted
`workspace_id` anywhere):

```python
def add_audit(workspace_id: int, campaign_id: int | None, actor: str, action: str,
              detail: str | None = None, target_id: int | None = None,
              draft_id: int | None = None) -> None: ...

def list_audit(workspace_id: int, campaign_id: int) -> list[sqlite3.Row]: ...
```

`list_audit` filters directly on `WHERE workspace_id = ? AND campaign_id = ?`
— **no time-window heuristic**, replacing v1's "two most recent rows near
campaign creation" approach, which was fragile and is now unnecessary since
`campaign_id` is a real column.

`create_campaign`, `list_campaigns`, `get_campaign`, `add_targets`,
`list_targets` are reused from v1 unchanged — they already follow the
workspace_id-required pattern correctly.

---

## 13. Route sequence (correction 6 — exact order)

`POST /campaigns` in `app/main.py`:

```python
@app.post("/campaigns")
def create_campaign(promoting_what: str = Form(...), target_type: str = Form(...),
                     workspace=Depends(get_current_workspace)):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)
    workspace_id = workspace["id"]
    settings = db.get_settings(workspace_id)

    # 1. Parse the Brief and retain IntakeStatus.
    intake_result = intake.parse_brief(promoting_what.strip(), target_type, settings)

    # 2. Create the campaign and obtain campaign_id.
    campaign_id = db.create_campaign(workspace_id, promoting_what.strip(),
                                      intake_result.brief.model_dump_json(), target_type)

    # 3. Write the intake audit row with workspace_id and campaign_id.
    intake_action, _, _ = audit_banners.INTAKE_MAP[intake_result.status]
    db.add_audit(workspace_id, campaign_id, "agent", intake_action, detail=intake_result.reason)

    # 4. Run discovery.
    discovery_result = sources.discover(intake_result.brief, settings)

    # 5. Write the discovery audit row with workspace_id and campaign_id.
    discovery_action, _, _ = audit_banners.DISCOVERY_MAP[discovery_result.status]
    db.add_audit(workspace_id, campaign_id, "agent", discovery_action, detail=discovery_result.reason)

    # 6. Save the returned targets.
    db.add_targets(workspace_id, campaign_id, discovery_result.candidates, discovery_result.source_used)

    # 7. Redirect to the campaign-detail route.
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)
```

This fixes v1's flaw of attempting an intake audit write before `campaign_id`
existed. No banner state is passed through query parameters — `GET
/campaigns/{id}` re-derives both banners directly from the two audit rows it
looks up via `db.list_audit(workspace_id, campaign_id)` (most recent
`intake.*` and `discovery.*` rows for that campaign), which is simpler and
removes v1's raw `?error=...` query-string interpolation entirely.

---

## 14. Verification (corrections 9 and 10)

### 14.1 Invalid-credential paths — isolated script, not UI-pasted fake keys

A temporary script (e.g. `scripts/verify_error_paths.py`, **not** under
`app/`, **not** part of the app, deleted before the final Slice 2 commit
unless deliberately converted into a maintained automated test) that:

- Calls `ApolloSource(api_key="invalid-test-key-not-a-real-credential").search(brief)`
  directly (an obviously-fake, hardcoded placeholder — never read from
  `outpost.db` or any settings) to exercise `INVALID_KEY`.
- Calls `llm.generate_structured(...)` with a workspace-settings-style dict
  containing an obviously-fake `gemini` key
  (`{"gemini": "invalid-test-gemini-key-not-real"}`) to exercise
  `INVALID_GEMINI_KEY`/`GEMINI_ERROR` and confirm which one Gemini's real API
  actually triggers (this also validates or corrects the `LLMError.kind`
  heuristic in §3 before it's relied on elsewhere).
- Imports and calls the **same** `DISCOVERY_MAP`/`INTAKE_MAP` from
  `app/audit_banners.py` used by `main.py`, so the printed output is
  guaranteed to match real app behavior, not a reimplementation.
- Prints, per case: result status, source attempted, source used, safe
  reason, selected audit action, selected banner text.
- **Makes zero database writes** — no `db.save_setting`, no `db.create_*`, no
  touching `outpost.db` at all. Pure in-process function calls, stdout only.
- Is removed before the Slice 2 implementation commit (or explicitly kept as
  a maintained test, a decision to be made and logged, not assumed).

### 14.2 Real insufficient-plan path — the owner's real key, never printed

Uses the owner's already-saved Apollo key (workspace_id 3, established in a
prior session) through the **normal app UI flow** — not the script. The key's
value is never printed or logged; only its presence/length may be inspected,
exactly as done previously (`SELECT length(key_value) FROM workspace_setting
...`, no `SELECT key_value`).

### 14.3 Functional verification checklist

1. Fresh-startup migration: `SELECT COUNT(*) FROM workspace_setting WHERE key_name='llm'` → 0 after startup.
2. No Apollo key (Demo Wellness Co, US-only brief): 6 US seed rows, info banner `discovery.no_apollo_key`, audit row confirmed via `list_audit`.
3. Real insufficient-plan Apollo key (workspace_id 3): seed rows show, warning banner names the plan restriction, `discovery.insufficient_plan` audit row. **This is the exact regression that motivated this corrected plan.**
4. Invalid Apollo key: via the isolated script (§14.1), not UI-pasted.
5. No Gemini key: heuristic intake banner, `intake.no_gemini_key` audit row.
6. Invalid Gemini key / Gemini error: via the isolated script (§14.1); confirms which of `INVALID_GEMINI_KEY`/`GEMINI_ERROR` actually fires.
7. Multi-country demo: brief mentioning "UK" and "Germany", no Gemini key, no Apollo key → heuristic extracts `["United Kingdom", "Germany"]` → seed filter returns only the 4 non-US rows.
8. Existing workspaces (Alpha, Beta) stay isolated: campaigns and audit rows scoped correctly, verified via direct DB query.
9. **Prefer computed-style checks over screenshots** (`getComputedStyle` assertions that banner foreground/background/spacing resolve from `--info`/`--warning`/`--space-4` tokens, matching the method already used successfully in Slices 0–2). **At most two screenshots for the entire slice**, taken only after every check above passes: one light-theme campaign-detail page, one dark-theme campaign-detail page.

---

## 15. Review of all Slice 2 scratch-branch changes (17 files)

`slice-2-scratch@96a01f8` touches 17 files. Every one is reviewed below.
"Reuse" means adopted with no behavioral change; "adapt" means the structure
is kept but specific changes are required per the corrections above; no
literal `git cherry-pick` command is intended anywhere in this table — these
are content-level review verdicts, applied by writing fresh files during
implementation.

| # | File | Type | Verdict | Reason |
|---|---|---|---|---|
| 1 | `app/models.py` | new | Adapt | `Brief`/`Candidate` shapes are right. Add module-level `TargetType` Literal, used by both `Brief.target_type` and `intake.parse_brief`'s signature. |
| 2 | `app/llm.py` | new | Adapt | Reuse the Gemini transport (URL, `key=` param, `responseMimeType`). Replace the retry with the schema-aware two-shot retry (§7) and add `LLMError`/`LLMErrorKind` so `INVALID_GEMINI_KEY` and `GEMINI_ERROR` (§3) are distinguishable — this did not exist in v1. |
| 3 | `app/agent/__init__.py` | new | Reuse | Empty package marker. |
| 4 | `app/agent/intake.py` | new | Adapt | Reuse the two-path shape and `_ParsedFields`. Return `IntakeResult` (brief, status, reason) instead of a bare `Brief`; add `_extract_countries` (§3.1); handle `LLMError.kind` to distinguish `INVALID_GEMINI_KEY` from `GEMINI_ERROR`. |
| 5 | `app/sources/__init__.py` | new | Adapt | Reuse the business/apollo-key routing idea. Rewrite `discover()` to always return one `SourceResult` per §5's exact fallback semantics, including the `source_attempted`/`source_used` distinction. |
| 6 | `app/sources/base.py` | new | Adapt | Interface shape (`name`, `search`, `evidence`, ABC) is right. Add `SourceStatus` and `SourceResult` so `search()` returns the shared contract for every source, not just some. |
| 7 | `app/sources/apollo.py` | new | Adapt | Reuse the HTTP call, body construction, and `_to_candidate` mapping (confirmed live). Replace the raising `ApolloError` with the non-raising `SourceResult`-returning flow (§4), including the sanitizing `_safe_reason` helper (§4.1). |
| 8 | `app/sources/seed.py` | new | Adapt | Reuse loading and `_to_candidate` mapping. Return `SourceResult(status=OK, ...)` per §2. Add country filtering (§11). |
| 9 | `app/templates/campaigns_list.html` | new | Reuse | Campaign table, click-through rows, empty state — all correct as built. |
| 10 | `app/templates/campaign_new.html` | new | Reuse | Intake form (textarea + target_type radios, creator disabled) is correct as built. |
| 11 | `app/templates/campaign_detail.html` | new | Adapt | Reuse page layout, brief chips, empty state. Change table columns to Company/Domain/Country/Size/Source (§10). Replace the single hardcoded data-source badge and single error banner with the two-banner stack (§9) driven by `list_audit`, not a query-string error. |
| 12 | `seeds/companies.json` | new | Adapt | Reuse 8 of 10 US entries; drop the 2 weakest; add 4 international (2 UK, 2 DE) — final 10 across 3 countries (§11). |
| 13 | `app/db.py` | modified | Adapt | Reuse the `campaign`/`target` table definitions and their CRUD functions unchanged. Add the final `audit` schema with `campaign_id` (§12), the `llm→gemini` migration, `add_audit`/`list_audit` (both `workspace_id`-required), and the `SETTING_KEYS` swap. |
| 14 | `app/main.py` | modified | Adapt | Reuse the `campaigns_list`/`new_campaign_form` routes unchanged. Rewrite `create_campaign` to the exact 7-step sequence in §13. Rewrite `campaign_detail` to load banners via `list_audit(workspace_id, campaign_id)`, not a query string. Rename the `llm` form param to `gemini` in `save_settings`. |
| 15 | `app/templates/base.html` | modified | Reuse | The Campaigns nav item with active-state logic is correct as built. |
| 16 | `app/static/css/app.css` | modified | Adapt | Reuse all v1 classes (page/table/chip/textarea/target-type/mono) — token-only, matches design.md. Add `.banners`, `.banner--info`, `.banner--warning` (§9) — existing tokens only. |
| 17 | `requirements.txt` | modified | Reuse | Add `httpx>=0.27`. Logged in DECISIONS.md. |

---

## 16. Files changed / created (implementation phase, not this commit)

**New:** `app/models.py`, `app/llm.py`, `app/agent/__init__.py`,
`app/agent/intake.py`, `app/sources/__init__.py`, `app/sources/base.py`,
`app/sources/apollo.py`, `app/sources/seed.py`, `app/audit_banners.py`,
`seeds/companies.json`, `app/templates/campaigns_list.html`,
`app/templates/campaign_new.html`, `app/templates/campaign_detail.html`,
a temporary `scripts/verify_error_paths.py` (deleted before the final commit
unless kept deliberately as a maintained test).
**Modified:** `app/db.py`, `app/main.py`, `app/templates/base.html`,
`app/templates/settings.html`, `app/static/css/app.css`, `requirements.txt`,
plus `PROGRESS.md`, `DECISIONS.md`, and `collaboration.md` at the end of the
slice.

**This commit** (the plan itself) touches only `SLICE_2_PLAN.md` and
`collaboration.md` — no application code.

---

## 17. Decisions to log in DECISIONS.md (at slice completion, not this commit)

- Every source's `search()` returns one shared `SourceResult` contract; no
  source ever raises past its own boundary.
- `discover()` owns fallback semantics and is the only place that knows *why*
  seed data was used; individual sources don't know they're a fallback.
- `IntakeStatus` distinguishes a rejected credential (`INVALID_GEMINI_KEY`)
  from every other failure mode (`GEMINI_ERROR`) — collapsing these was a
  real defect in the earlier draft.
- `audit` table's final schema includes `campaign_id` from the start; no
  interim schema without it was ever shipped.
- Settings key renamed `llm` → `gemini` with an idempotent startup migration.
- New dependency: `httpx`, one client for both Apollo and Gemini REST calls.
- Retry re-derives the call from the schema and the validation error, rather
  than repeating the identical request.

---

## 18. Model recommendation for execution

All architectural decisions in this plan are settled: the shared `SourceResult`
contract, the four/five-way status mappings, the corrected route sequence, the
final audit schema, and the country-extraction heuristic. Implementation is
refactoring the reviewed v1 files per §15's adapt/reuse verdicts, writing one
new small mapping module, and one temporary verification script.
**Recommended execution model: Sonnet.** State this again at the start of
implementation so the owner can confirm the model switch before work begins.
