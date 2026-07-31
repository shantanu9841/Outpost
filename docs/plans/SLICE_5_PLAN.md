# Slice 5 Plan — Creator sources and demo mode

**Status:** Planning only. Owner-approved on 2026-07-31 with the ten decisions
in §1; SDE 2's owner-approved implementation-readiness corrections are now
incorporated. No application code, tests, seeds, templates, or schema change is
part of this commit. Implementation does not begin until the owner gives final
approval and confirms the model switch.

**Model:** Planned on Opus. Execution recommendation is **Sonnet** (mechanical
implementation from this approved plan); confirm the switch at the top of
implementation, per `CLAUDE.md`.

**Baseline:** branch `codex/sde-1-slice-2-hardening` at `d54c0d8`, clean tree,
**171 passing tests** (`python -m unittest discover -s tests`).

---

## 1. Owner-approved decisions (authoritative)

1. **Routing — deterministic priority, no auto-aggregation.** Creator
   discovery selects exactly one source: **Apify when configured → else
   YouTube when configured → else creator seed.** Apify and YouTube are never
   automatically aggregated in Slice 5.
2. **Apify — run both actors and merge normalized candidates.** One
   `ApifySource.search()` runs the Instagram and TikTok actors and merges
   their normalized candidates:
   - Both succeed → merged results.
   - One succeeds → that platform's candidates plus a sanitized
     partial-results warning and auditable provenance (which platform failed
     and why).
   - Both fail → a single typed failure; `discover()` falls back to creator
     seed using the existing safe fallback semantics.
   - Differing failures resolve by the deterministic precedence in §5.3.
3. **Creator scoring — target-type-aware additive heuristic.** Components:
   followers **25**, niche/bio overlap **60**, country **15**. The business
   scoring path and its existing anchor scores are unchanged.
4. **Seed data — full discrimination spread.** Creator seed includes strong,
   partial, geographic-mismatch, weak/low-follower, and completely irrelevant
   examples so ranking discrimination is demonstrable on the zero-key path.
5. **YouTube — workspace key required for live.** Live YouTube requires the
   workspace `youtube` key. Without it, creator discovery uses seed data.
   YouTube is **not** described anywhere as offering keyless live discovery.
   (This corrects SPEC §5 and the Settings hint. No `YOUTUBE_API_KEY` env
   fallback — a workspace key is required, per this decision.)
6. **YouTube quota — official current model.** `search.list` has its own
   dedicated bucket: a default allowance of **100 calls/day, 1 unit per
   call**. The separate **10,000 units/day** pool is for all other endpoints
   combined. `channels.list` is a batched enrichment request costing 1 unit
   from that shared pool. The outdated "100 units per call against 10,000
   units/day" claim is removed.
7. **Apify pricing — official current figures (time-sensitive).** See §4.3.
8. **Provider contracts — documented from official schemas; live error
   mappings remain explicit assumptions** until safely verified (§4, §5.4).
   Never expose API keys, credential-bearing URLs, or raw provider errors.
9. **Normalizer contract — `evidence_for(source_used, target_type,
   candidate)`** so business and creator seed evidence cannot collide (§6.2).
10. **Scope control — plan and collaboration docs only.** No implementation.

---

## 2. Scope

**In scope**

- `app/sources/youtube.py` and `app/sources/apify.py` behind the existing
  `Source` / `SourceResult` contract.
- Creator seed data (`seeds/creators.json`) and `SeedSource("creator")`
  reading it (today it returns empty).
- Creator evidence normalization and the `evidence_for` contract extension.
- A target-type-aware creator branch in the scoring heuristic.
- `discover()` creator routing and fallback.
- Creator discovery audit actions and banners (source-accurate wording).
- UI: enable creator campaigns; render creator columns; correct the Settings
  YouTube hint.
- A complete zero-key creator demo path.

**Out of scope (unchanged)**

- Intake, drafting, approval queue, pipeline (Slice 4); eval and cost-aware
  routing (Slice 6). Nothing sends or posts. No message-send integration.
- No schema migration: `target.source`, `target.reach`, `target.location`,
  and `target.raw_json` already carry creator data; `Candidate` already
  documents `source` (`youtube`, `apify`) and `reach` ("subscribers for
  creators").

---

## 3. Non-negotiables honored

- **BYO-key.** YouTube uses the workspace `youtube` key; Apify uses the
  workspace `apify` token via Apify's REST start-run and polling endpoints,
  authenticated with an `Authorization: Bearer` header (§4.0). The builder
  never supplies or is billed for a provider key.
- **Demo mode.** With zero keys, a creator campaign completes end to end on
  creator seed data.
- **Source-agnostic.** Both new sources implement the shared `Source`
  interface and return the shared `SourceResult`; routes and downstream agents
  never read provider-specific payloads.
- **Structured output / human approval / atomic audit / tenant isolation.**
  Unchanged; creator targets flow through the same scoring, drafting,
  approval, pipeline, and audit machinery.

---

## 4. Provider contracts (verified 2026-07-31)

Pricing and quota facts are **time-sensitive**; verification date and official
sources are recorded below. Live HTTP-status → typed-status mappings in §5.4
are **assumptions** until confirmed by the §7.2 verification script.

### 4.0 Apify transport, authentication, and run caps (shared by both actors)

Corrections 2 and 3: never put the token in a URL, and bound every run's
duration and cost.

- **Authentication — header, never query param (correction 2).** All Apify
  requests send `Authorization: Bearer <workspace apify key>`. The token is
  never a query parameter, so no request URL is ever credential-bearing.
  Official Apify guidance: "Using your token in the request header is more
  secure than using it as a URL parameter because URLs are often stored in
  browser history and server logs"
  (https://docs.apify.com/api/v2). `_safe_reason` still redacts any echoed
  token defensively.
- **Start-run + bounded polling, not run-sync (correction 3).** Apify's
  `run-sync-get-dataset-items` endpoint waits up to 300 s on one held
  connection and is not robust for a new integration. Instead:
  1. **Start:** `POST https://api.apify.com/v2/actors/<actorId>/runs` with the
     JSON input body and the Bearer header, plus run-bounding query
     parameters (all confirmed official at
     https://docs.apify.com/api/v2/actors-runs-post). Use the canonical
     `/v2/actors/` prefix for this new integration; `/v2/acts/` is a
     deprecated compatibility alias and must not be introduced:
     - `timeout=<run_timeout_secs>` — hard actor-run duration cap (default
       **120**).
     - `maxItems=<N>` — caps the number of charged pay-per-result items
       (set to the per-actor search limit, default **10**).
     - `maxTotalChargeUsd=<cap>` — hard ceiling on total run cost (default
       **0.10**).
     - `memory=<MB>` — left at the actor default unless tuning is needed.
  2. **Poll:** `GET https://api.apify.com/v2/actor-runs/<runId>` with the
     Bearer header, every ~3 s, until the run reaches a terminal status
     (`SUCCEEDED`, `FAILED`, `ABORTED`, `TIMED-OUT`) or a **wall-clock poll
     budget (default 150 s)** is exhausted.
  3. **Fetch:** on `SUCCEEDED`, `GET
     https://api.apify.com/v2/datasets/<defaultDatasetId>/items` (the run's
     `defaultDatasetId`) with the Bearer header.
  - **Per-request `httpx` timeout** is a separate, strict cap (default
    **30 s**) on each individual start/poll/fetch call, independent of the
    actor-run `timeout`.
  - **Status handling:** a non-`SUCCEEDED` terminal status or an exhausted
    poll budget maps to `PROVIDER_ERROR` (run failure) or `NETWORK_ERROR`
    (transport/timeout) per §5.4, never a raise. All defaults above are
    single named constants in `apify.py`, easy for the owner to adjust.

### 4.1 Apify — Instagram (`apify/instagram-scraper`, id `shu8hvrXbJbY3Eb9W`)

- **Transport/auth/caps:** per §4.0 (Bearer header, start-run + bounded
  polling, per-run item and cost caps).
- **Discovery input (creator search):**
  `{"resultsType": "details", "search": <niche>, "searchType": "user",
  "searchLimit": N}` (default `N = 10`).
- **Output fields used (from the official input schema / README):**
  `fullName`, `username`, `followersCount`, `biography`,
  `verified`/`isBusinessAccount`. Country is generally absent for IG profiles.

### 4.2 Apify — TikTok (`clockworks/tiktok-scraper`, id `GdWCkxBtKWOsKjdch`)

- **Transport/auth/caps:** per §4.0.
- **Discovery input (creator search):**
  `{"searchQueries": [<niche>], "searchSection": "/user",
  "maxProfilesPerQuery": N}` (default `N = 10`). Note the schema's own caveat:
  `maxProfilesPerQuery` governs profile-search counts; `resultsPerPage` is for
  hashtag/profile video counts and is not used for creator discovery.
- **Output fields used (from the official input schema / README):** display
  `name`/`nickname`, unique id/handle, `fans`/`followers` count, `signature`
  /bio. Country generally absent.

### 4.3 Pricing (official, 2026-07-31 — time-sensitive)

| Actor | Official figure | Source |
|---|---|---|
| `apify/instagram-scraper` | **$2.70 / 1,000 results** on the Free plan ("with no discount applied") | https://apify.com/apify/instagram-scraper |
| `clockworks/tiktok-scraper` | Advertised **from $1.70 / 1,000 results** (lowest tier); the **Free-plan tier is $3.70 / 1,000** per the actor's tiered pricing table, plus a $0.001 actor-start fee | https://apify.com/clockworks/tiktok-scraper |

Both are pay-per-result on the **owner's** Apify account (BYO-key). Prices are
provider-controlled and may change; re-verify before relying on a figure.

### 4.4 YouTube Data API v3

- **Transport:** `GET https://www.googleapis.com/youtube/v3/search` with
  `part=snippet&type=channel&q=<niche>&maxResults=N`, then one batched
  `GET .../youtube/v3/channels` with `part=snippet,statistics&id=<comma-joined
  ids>` to enrich with `subscriberCount` and channel `country`. The key is
  sent in the **`X-goog-api-key` request header**, not the `key=` query
  parameter, for the same reason as Apify (correction 2) — no request URL is
  credential-bearing. Each call has a strict per-request `httpx` timeout
  (default 30 s), and `_safe_reason` redacts any echoed key defensively.
- **Quota (official, 2026-07-31 —
  https://developers.google.com/youtube/v3/determine_quota_cost):**
  `search.list` has its **own dedicated bucket, default 100 calls/day at 1
  unit each**. A separate **10,000 units/day** pool covers all other
  endpoints; `channels.list` costs 1 unit from that pool. Free of charge; a
  Google Cloud project and API key are required for every call (there is **no
  keyless access**).
- **Output fields used:** channel `title`, channel `description` (niche/bio),
  `subscriberCount` (reach), channel `country` when present, channel id
  (handle/external id).

---

## 5. Architecture

### 5.1 `discover()` creator routing (`app/sources/__init__.py`)

Replace today's placeholder creator branch. Business routing is unchanged.

```
if brief.target_type == "creator":
    return _discover_creator(brief, settings)
# ... existing business (Apollo-or-seed) path unchanged ...
```

`_discover_creator(brief, settings)` — deterministic priority (decision 1):

1. If `settings.get("apify")`: `result = ApifySource(key).search(brief)`.
   - `status in {OK, PARTIAL_RESULTS}` → return `result` (do **not** fall
     back; partial still has candidates).
   - otherwise → `_fallback_to_creator_seed(brief, result.status,
     result.reason)`.
2. elif `settings.get("youtube")`: `result = YouTubeSource(key).search(brief)`.
   - `status == OK` → return `result`.
   - otherwise → `_fallback_to_creator_seed(brief, result.status,
     result.reason)`.
3. else (no creator key at all) → `_fallback_to_creator_seed(brief,
   SourceStatus.NO_KEY, None)`.

`_fallback_to_creator_seed` mirrors the existing `_fallback_to_seed`: it serves
`SeedSource("creator")` data tagged with the *primary* (live-source) status
and sanitized reason, and only returns `SEED_ERROR` (no candidates) if the
creator seed itself fails to load — never claiming seed data was shown when it
was not. `source_attempted` is the attempted live source (`"apify"` or
`"youtube"`, or `"youtube"` as the nominal default when no creator key is set),
`source_used` is `"seed"`.

### 5.2 `SourceStatus.PARTIAL_RESULTS` (new)

Add one status to the shared enum:

```
PARTIAL_RESULTS = "partial_results"  # multi-actor source: >=1 sub-source
                                     # succeeded, >=1 failed; candidates exist
```

`discover()` treats `PARTIAL_RESULTS` as a success for the "use these
candidates, do not fall back" decision, while the audit/banner map (§6.3)
renders a **warning** naming the missing platform. This is the honest
representation of "we have results, but not all of them," and generalizes to
any future multi-sub-source provider.

### 5.3 `ApifySource` (merge + precedence)

`ApifySource.search(brief)` runs a private per-actor helper twice (Instagram,
then TikTok). Each helper performs the §4.0 start-run → bounded-poll → fetch
sequence for its actor and returns `(candidates, sub_status, sub_reason)` with
the §5.4 mapping and a sanitizing `_safe_reason` (never key/URL/raw payload).
The two runs are sequential and each is bounded by the §4.0 per-request
timeout, actor-run `timeout`, poll budget, `maxItems`, and
`maxTotalChargeUsd`, so total latency and spend are strictly capped. It then
combines:

- **Both OK** → `SourceResult(merged, OK, "apify", "apify", None)`.
- **Exactly one OK** → `SourceResult(that platform's candidates,
  PARTIAL_RESULTS, "apify", "apify", reason=<sanitized: "<failed platform>
  unavailable (<sub_reason>); showing <ok platform> only">)`. Provenance
  (which platform failed, sanitized reason) is carried in `reason` and written
  to the audit detail.
- **Both fail** → `SourceResult([], <precedence status>, "apify", "apify",
  reason=<sanitized combined: "instagram: <r1>; tiktok: <r2>">)`.

**Deterministic failure precedence (decision 2):** when the two sub-statuses
differ, the reported status is the higher-priority one by this fixed order
(most actionable/credential-relevant first):

```
INVALID_KEY > INSUFFICIENT_PLAN > RATE_LIMITED > PROVIDER_ERROR > NETWORK_ERROR
```

Equal statuses report that status. The combined `reason` always names both
platforms' sanitized sub-reasons regardless of which status wins, so no
provenance is lost.

### 5.4 Live HTTP-status → typed-status mappings (ASSUMPTIONS — verify in §7.2)

- **Apify (per actor).** On the *start-run* call: `401` → `INVALID_KEY`;
  `402`/`403` → `INSUFFICIENT_PLAN` (out of credit / plan limit); `429` →
  `RATE_LIMITED`; `httpx.RequestError`/per-request timeout → `NETWORK_ERROR`;
  any other non-2xx → `PROVIDER_ERROR`. On the *run lifecycle*: a terminal
  status of `FAILED`/`ABORTED`/`TIMED-OUT`, or an exhausted poll budget, →
  `PROVIDER_ERROR`; a transport error while polling/fetching → `NETWORK_ERROR`.
  The dataset-items body is a JSON array; a non-array or item-shape violation
  is `PROVIDER_ERROR`, never a raise.
- **YouTube:** `400` with an "API key not valid" message or `403` reason
  `keyInvalid` → `INVALID_KEY`; `403` reason `quotaExceeded`/`rateLimitExceeded`
  → `RATE_LIMITED`; timeout/transport → `NETWORK_ERROR`; else → `PROVIDER_ERROR`.

Because both providers authenticate via a request header (§4.0, §4.4), no
request URL is credential-bearing; `_safe_reason` additionally redacts any
echoed token/key. These status mappings remain explicitly labelled assumptions
in code comments and in `PROGRESS.md`'s "Known limitations" until §7.2 confirms
them live, exactly as Slice 2 did for Apollo/Gemini.

### 5.5 `YouTubeSource`

`search(brief)` performs the `search.list` channel query, then one batched
`channels.list` enrichment (both authenticated via the `X-goog-api-key` header,
§4.4), maps to `Candidate` (`source="youtube"`), and returns a `SourceResult`.
Never raises past its boundary; `_safe_reason` sanitizes. Requires the
workspace `youtube` key (decision 5); the caller only constructs it when that
key is present.

---

## 6. Evidence, scoring, audit

### 6.1 Creator evidence shape (source-neutral)

```
{"name": <canonical_name>, "niche": <bio/description text>,
 "followers": <coerce_int(...)>, "country": <str|None>,
 "handle": <str|None>, "platform": "youtube"|"instagram"|"tiktok"}
```

`name` via `canonical_name` (guarantees the nonblank "name" the heuristic's
final fallback and `assert_grounded` rely on); `followers` via `coerce_int`.
Each creator source's `normalize_evidence` maps its own raw fields into this
one shape, so scoring never reads provider-specific keys.

**Persisted platform provenance.** `target.source` remains the source-level
value (`"youtube"`, `"apify"`, or `"seed"`) required by the existing shared
contract; an Apify batch therefore does not overload it with actor-specific
values. Instead, every creator source adds a controlled
`raw["_outpost_platform"]` value (`"youtube"`, `"instagram"`, or `"tiktok"`)
when constructing each `Candidate`. This marker is set from the selected
source/actor constant, never copied from an untrusted provider field. Creator
seed rows receive the same controlled marker during candidate construction.
The evidence normalizers use that marker for the canonical `platform` field,
and `campaign_detail` exposes it to the template as `target["platform"]` after
reading persisted `raw_json`. This preserves Instagram/TikTok identity through
the existing batch-level `source_name="apify"` database write without a schema
migration or provider-shape logic in the template.

### 6.2 `evidence_for(source_used, target_type, candidate)` (decision 9)

The current registry keys normalizers by `source_used` alone, but seed serves
both business and creator rows under `source_used == "seed"` — a collision.
The registry becomes:

```
_EVIDENCE_NORMALIZERS = {
    "apollo":  _apollo_evidence,        # business
    "youtube": _youtube_evidence,       # creator
    "apify":   _apify_evidence,         # creator
    "seed":    {"business": _seed_business_evidence,
                "creator":  _seed_creator_evidence},
}
```

`evidence_for(source_used, target_type, candidate)` dispatches the `seed`
entry by `target_type` and single-shape sources by name. `app/main.py` already
holds `brief.target_type` at the call site (step 7 of `create_campaign`), so
this is a one-line change there plus the registry. Recorded as an active
decision in `DECISIONS.md`.

Scoring has two paths — the LLM path and the deterministic heuristic — and
**both** must become target-type-aware (correction 1). Today's business
wording lives in `app/agent/scoring.py`.

#### 6.3.1 LLM path — target-type-aware prompt (correction 1)

The current `SYSTEM_PROMPT` says "You score how well each candidate **company**
fits a **business's** outreach campaign," and `_build_prompt` sends the brief
fields but **not** `target_type`. A creator campaign scored with Gemini would
therefore be told to score companies — wrong. The plan makes the prompt
target-type-aware:

- `SYSTEM_PROMPT` becomes two wordings selected by `brief.target_type`: the
  business wording is preserved verbatim (so business LLM behavior is
  unchanged), and a creator wording scores "how well each **creator** fits the
  campaign," citing a specific evidence field/value from that creator's own
  evidence (same grounded-citation contract).
- `_build_prompt(brief, evidence_list)` includes `target_type` and labels each
  row's evidence appropriately (creator vs company). It already emits
  `niche_or_industry`, `audience`, `product`, and `target_countries`, which are
  meaningful for both types.
- `score_batch`/`FitBatch`/`FitAssessment`/`FitReason` schemas, the two-shot
  validation retry, grounding (`_is_grounded`), and `assert_grounded` are
  unchanged and shape-agnostic — only the prompt text and the `target_type`
  it carries change. The heuristic is prompt-independent, so this change
  cannot move any business or creator heuristic score.

#### 6.3.2 Heuristic path — creator branch (decision 3)

`_heuristic()` branches on `brief.target_type`:

- **business (unchanged):** industry overlap 0–60, size band 0–25, country
  0–15. Byte-identical; the Slice 3 anchor-score tests must still pass.
- **creator (new, additive):** niche/bio overlap 0–**60** (reusing
  `_significant_niche_tokens` / stemming against the `niche` field), followers
  band 0–**25** (§6.3.3, creator-appropriate reason text — never "employees" or
  "distribution/logistics"), country 0–**15**. Every emitted reason cites a
  present, nonblank evidence value; a component whose field is missing
  contributes 0 and emits no reason; the name-only final fallback and
  `assert_grounded` generalize unchanged.

#### 6.3.3 Creator follower bands (correction 5)

The 0–25 follower component uses these exact, inclusive bands on the integer
`followers` evidence value (chosen for outreach fit: an established but still
reachable micro/mid creator scores highest; a tiny account or an
out-of-reach mega account scores lowest):

| Followers (inclusive) | Points | Reason text |
|---|---|---|
| 10,000 – 500,000 | **25** | "Audience size (N followers) is a strong fit for creator outreach" |
| 1,000 – 9,999, or 500,001 – 2,000,000 | **15** | "Audience size (N followers) is a moderate fit" |
| < 1,000, or > 2,000,000 | **5** | "Audience size (N followers) is outside the ideal range" |
| missing / non-integer | **0** | (no reason emitted) |

Boundary behavior (explicit, mirroring the business band's inclusive style):
`999`→5, `1,000`→15, `9,999`→15, `10,000`→25, `500,000`→25, `500,001`→15,
`2,000,000`→15, `2,000,001`→5. `followers` is coerced via `coerce_int`, so a
`bool`, `NaN`/`inf`, non-integral float, or unparseable string becomes missing
(0 points, no reason), never a crash. §7.1 adds a boundary test for each pair.

**Practical maximum without country.** Instagram and TikTok profiles commonly
have **no country** field, so their country component scores 0 and the
practical maximum for such a creator is **85** (60 niche + 25 followers), not
100. This is expected and honest — a missing field never fabricates a citation
— and the seed spread (§7.4) and tests treat 85 as the effective creator
ceiling where country is absent.

### 6.4 Audit and banners (`app/audit_banners.py`)

Today's `DISCOVERY_MAP` is Apollo-worded. Add explicit creator discovery
actions + banners selected by `source_attempted`, following the existing
"no enum-string interpolation" discipline (explicit maps, added to
`ACTION_LABELS` and `BANNER_BY_ACTION`). New actions include, at minimum:

- `discovery.youtube_ok`, `discovery.apify_ok` (silent),
- `discovery.apify_partial` (**warning**, names the missing platform),
- `discovery.no_creator_key` (**info**: using creator seed; add an Apify or
  YouTube key for live discovery),
- `discovery.creator_invalid_key`, `discovery.creator_insufficient_plan`,
  `discovery.creator_rate_limited`, `discovery.creator_provider_error`,
  `discovery.creator_network_error` (**warning**, source-accurate wording),
- `discovery.creator_seed_error` (**warning**).

**No action-key collision (correction 6):** `BANNER_BY_ACTION` and
`ACTION_LABELS` are global, single-namespace maps keyed by action string.
Business discovery already owns `discovery.seed_error`, so the creator
seed-load failure uses the distinct `discovery.creator_seed_error` (never the
business key). Every creator discovery action above is likewise namespaced
(`discovery.creator_*`, `discovery.youtube_ok`, `discovery.apify_ok`,
`discovery.apify_partial`, `discovery.no_creator_key`) so no creator entry can
overwrite or be overwritten by a business entry. A test asserts the business
and creator discovery maps share no action key.

`main.py` selects the business vs creator map by `discovery_result.
source_attempted`. All banner detail is the already-sanitized `reason`; no raw
provider text or credential ever reaches the audit table or the UI.

---

## 7. Verification and acceptance criteria

Verification is proportional to risk (collaboration.md rule 9): tenant
isolation, credential/fallback behavior, and provenance require retained
automated tests plus targeted DB/UI checks. Baseline after Slice 5: the
existing **171 tests still pass**, plus the new creator tests.

### 7.1 Retained automated tests (`tests/test_slice5_creators.py`, mocked)

Every provider call is mocked at the `httpx` boundary — no live call, no real
key, no `outpost.db` writes (temp SQLite where a DB is touched). Acceptance
criteria, each with at least one test:

1. **Apify full success:** both actors return profiles → merged candidates,
   `status == OK`, `source_used == "apify"`, no banner.
2. **Apify partial success:** one actor OK, one fails → the OK platform's
   candidates, `status == PARTIAL_RESULTS`, a sanitized warning naming the
   failed platform, and audit provenance recording which failed and why.
3. **Apify dual failure:** both actors fail → `discover()` falls back to
   creator seed; the preserved status/reason is the primary live failure, and
   candidates come from seed (or `SEED_ERROR`/no candidates if seed also
   fails).
4. **Status precedence:** differing dual failures resolve to the §5.3 order
   (e.g. `INVALID_KEY` beats `RATE_LIMITED`); both sub-reasons appear in the
   combined sanitized reason.
5. **YouTube routing:** creator + `youtube` key (no `apify` key) → YouTube
   path; creator + `apify` key present → Apify path takes priority (YouTube
   not called).
6. **Seed fallback / zero-key routing:** creator + no creator key → creator
   seed, `discovery.no_creator_key` info banner, audited.
7. **Creator scoring:** the seed spread (§7.4) produces a demonstrable ranking
   — strong > partial > geographic-mismatch/weak > irrelevant — with grounded,
   creator-appropriate reasons; every score has ≥1 grounded citation.
8. **Follower boundary bands (correction 5):** one test per §6.3.3 boundary
   pair — `999`/`1,000`, `9,999`/`10,000`, `500,000`/`500,001`,
   `2,000,000`/`2,000,001` — asserting the exact points, plus a
   missing/non-integer `followers` case scoring 0 with no reason, plus a
   country-absent creator whose total is capped at the practical maximum of
   **85**.
9. **Target-type-aware LLM prompt (correction 1):** with the LLM mocked, a
   creator campaign's built prompt/system text describes creators (not
   "candidate company") and carries `target_type`, while a business campaign's
   prompt is unchanged; both still parse and ground identically.
10. **Business-score regression protection:** the Slice 3 anchor-score table
    and business heuristic outputs are unchanged (existing tests re-run green;
    an explicit assertion pins a business anchor).
11. **Audit action-key non-collision (correction 6):** the business and
    creator discovery maps share no action key; every creator entry resolves
    through `BANNER_BY_ACTION`/`ACTION_LABELS` to its own creator-worded
    banner/label.
12. **Tenant isolation:** creator targets, audit rows, and drafts never cross
    workspaces (scoped query checks, as in Slice 2/4).
13. **Sanitized audit details:** no test fixture or asserted audit/banner
    string contains a key, a credential-bearing URL, or a raw provider payload;
    an injected fake key inside a provider error is redacted before audit.
14. **Zero-key demo (integration-style, mocked/seed):** creator campaign →
    seed discovery → creator scoring → draft → approve → pipeline completes.
15. **Transport authentication and bounds (corrections 2/3):** mocked request
    assertions prove every Apify start/poll/fetch call sends the Bearer header
    and no `token` query parameter; every YouTube call sends
    `X-goog-api-key` and no `key` query parameter; both Apify actor starts carry
    `timeout`, `maxItems`, and `maxTotalChargeUsd`; every HTTP call receives the
    configured per-request timeout; the poll loop uses a mocked monotonic
    clock/sleep and cannot exceed its wall-clock budget; and start, poll, and
    fetch non-2xx/transport failures plus every transitional/terminal run state
    map without raising. No retained test performs a real provider call.
16. **Platform provenance and rendering:** merged Apify results retain distinct
    controlled `_outpost_platform` values through persistence, evidence, and
    the campaign-detail view; Instagram, TikTok, YouTube, and creator-seed rows
    each render the expected platform label while `target.source` remains
    `apify`, `youtube`, or `seed` as appropriate.

### 7.2 Safe live verification (deletable script, §14.1 pattern)

A temporary, DB-write-free script may live-check only safely reproducible
cases: an obviously invalid synthetic credential and, when the owner has
provided a workspace key and authorized its use, one bounded happy-path call.
It must never intentionally exhaust quota, provoke rate limiting, consume an
account's remaining credit, manufacture an insufficient-plan/billing failure,
or force a paid actor failure. Invalid-key checks use only synthetic values;
owner keys are consumed in-process via `db.get_settings()` and are never read,
printed, copied into the script, or placed in a URL.

All other §5.4 mappings must be established by current official documentation
and the mocked retained tests in §7.1. A naturally occurring live failure may be
recorded as an observed case only after its detail is sanitized; it must not be
induced. The temporary script is deleted after the safe checks
(`collaboration.md` rule 11). Any mapping not safely observed remains labelled
an assumption in code and `PROGRESS.md`; implementation does not wait for an
unsafe reproduction.

### 7.3 Live happy-path (only if the owner provides keys)

If the owner pastes a `youtube` and/or `apify` key into a workspace via
Settings, verify one live creator campaign end to end. The key is stored once
in local, workspace-scoped SQLite (`workspace_setting.key_value`, masked in the
UI) — that is where BYO-keys live (correction 4). It is never copied into
scripts, logs, audit details, request URLs, screenshots, or any tracked file,
and provider code consumes it only via `db.get_settings()`. Otherwise
verification is seed + mocked, which is honest but not a live end-to-end —
recorded as a limitation.

### 7.4 Creator seed spread (decision 4)

`seeds/creators.json` includes, at minimum, one each of: **strong** fit,
**partial** fit, **geographic mismatch** (right niche, wrong country),
**weak/low-follower**, and **completely irrelevant** creator — so the heuristic
ranking is visibly discriminating on the zero-key path without a live LLM.

### 7.5 UI / design

- `campaign_new.html`: enable the creator radio (remove `disabled` and the
  "coming in Slice 5" label).
- `campaign_detail.html`: target-type-aware table (Creator / Handle / Platform
  / Followers for creators vs Company / Domain / Country / Size for business);
  fit-reasons expander and draft CTA unchanged; design.md tokens only; light
  and dark verified via computed-style checks; ≤2 final screenshots.
- `settings.html`: correct the YouTube hint to state that a workspace key
  enables live YouTube's free-quota discovery and that, without a key, creators
  use seed data (no "keyless live" language).

---

## 8. Files touched by the implementation (for reference — not this commit)

New: `app/sources/youtube.py`, `app/sources/apify.py`, `seeds/creators.json`,
`tests/test_slice5_creators.py`.
Modified: `app/sources/__init__.py`, `app/sources/base.py`
(`PARTIAL_RESULTS`), `app/sources/seed.py`, `app/agent/scoring.py`,
`app/audit_banners.py`, `app/main.py`, `app/templates/campaign_new.html`,
`app/templates/campaign_detail.html`, `app/templates/settings.html`,
`PROGRESS.md`, `DECISIONS.md`, `docs/history/COLLABORATION_LOG.md`,
`collaboration.md`. No `requirements.txt` change (`httpx` already present). No
schema migration.

**This commit** touches only `docs/plans/SLICE_5_PLAN.md`, `PROGRESS.md`,
`collaboration.md`, and `docs/history/COLLABORATION_LOG.md`.

---

## 9. Remaining assumptions requiring live verification

- Apify and YouTube HTTP-status → typed-status mappings, including Apify
  run-lifecycle terminal states (§5.4), must be grounded during implementation
  in official documentation and mocked retained tests. §7.2 may live-observe
  only a synthetic invalid-key case and owner-authorized bounded happy paths;
  rate-limit, quota, insufficient-plan/billing, and forced-run-failure mappings
  must never be
  deliberately reproduced. Naturally observed sanitized failures may be
  recorded separately. Unobserved mappings remain explicit assumptions. The
  header-auth schemes (Bearer for Apify, `X-goog-api-key` for YouTube) and the
  run-bounding parameters (`timeout`, `maxItems`, `maxTotalChargeUsd`) are
  confirmed against official docs (§4.0, §4.4).
- Provider pricing (§4.3) and the YouTube quota model (§4.4) are current as of
  2026-07-31 and provider-controlled; re-verify before relying on a figure.
- Exact Apify output field names (e.g. TikTok `fans` vs `followers`) and the
  run's `defaultDatasetId` shape are taken from the official schemas/READMEs
  and should be confirmed against a real run/dataset item during
  implementation; the normalizer must tolerate a missing field (→ `None`)
  rather than raise.
- The creator follower bands (§6.3.3) are a demo-mode heuristic choice, not a
  calibrated model; thresholds are documented so behavior is deterministic and
  testable, not because they are externally validated.
- Live creator end-to-end (§7.3) depends on the owner providing a free YouTube
  and/or Apify key; absent that, verification is seed + mocked.
