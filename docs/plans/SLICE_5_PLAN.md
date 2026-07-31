# Slice 5 Plan — Creator sources and demo mode

**Status:** Planning only. Owner-approved on 2026-07-31 with the ten decisions
in §1. No application code, tests, seeds, templates, or schema change is part
of this commit. Implementation does not begin until the owner (and SDE 2's
review) confirm this plan and the model switch.

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
  workspace `apify` token via Apify's REST run-sync endpoint. The builder
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

### 4.1 Apify — Instagram (`apify/instagram-scraper`, id `shu8hvrXbJbY3Eb9W`)

- **Transport:** `POST
  https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items?token=<workspace apify key>`
  with a JSON input body; returns dataset items directly (synchronous, same
  `httpx` shape as `apollo.py`). The token is a query parameter, so the
  request URL is credential-bearing and must never be logged or interpolated
  into a reason (mirrors `llm.py`'s Gemini-URL handling).
- **Discovery input (creator search):**
  `{"resultsType": "details", "search": <niche>, "searchType": "user",
  "searchLimit": N}` (default `N = 10`).
- **Output fields used (from the official input schema / README):**
  `fullName`, `username`, `followersCount`, `biography`,
  `verified`/`isBusinessAccount`. Country is generally absent for IG profiles.

### 4.2 Apify — TikTok (`clockworks/tiktok-scraper`, id `GdWCkxBtKWOsKjdch`)

- **Transport:** `POST
  https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items?token=<workspace apify key>`.
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

- **Transport:** `GET
  https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q=<niche>&maxResults=N&key=<workspace youtube key>`,
  then one batched `channels.list?part=snippet,statistics&id=<comma-joined
  ids>&key=…` to enrich with `subscriberCount` and channel `country`.
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
then TikTok), each returning `(candidates, sub_status, sub_reason)` with the
§5.4 mapping and a sanitizing `_safe_reason` (never key/URL/raw payload). It
then combines:

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

- **Apify (per actor):** `401` → `INVALID_KEY`; `402`/`403` →
  `INSUFFICIENT_PLAN` (out of credit / plan limit); `429` → `RATE_LIMITED`;
  `httpx.RequestError`/timeout → `NETWORK_ERROR`; any other non-2xx or a
  malformed 2xx body → `PROVIDER_ERROR`. A run-sync response is a JSON array of
  dataset items; a non-array or item-shape violation is `PROVIDER_ERROR`, never
  a raise.
- **YouTube:** `400` with an "API key not valid" message or `403` reason
  `keyInvalid` → `INVALID_KEY`; `403` reason `quotaExceeded`/`rateLimitExceeded`
  → `RATE_LIMITED`; timeout/transport → `NETWORK_ERROR`; else → `PROVIDER_ERROR`.

These remain explicitly labelled assumptions in code comments and in
`PROGRESS.md`'s "Known limitations" until §7.2 confirms them live, exactly as
Slice 2 did for Apollo/Gemini.

### 5.5 `YouTubeSource`

`search(brief)` performs the `search.list` channel query, then one batched
`channels.list` enrichment, maps to `Candidate` (`source="youtube"`), and
returns a `SourceResult`. Never raises past its boundary; `_safe_reason`
sanitizes. Requires the workspace `youtube` key (decision 5); the caller only
constructs it when that key is present.

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

### 6.3 Scoring — creator heuristic branch (decision 3)

`_heuristic()` branches on `brief.target_type`:

- **business (unchanged):** industry overlap 0–60, size band 0–25, country
  0–15. Byte-identical; the Slice 3 anchor-score tests must still pass.
- **creator (new, additive):** niche/bio overlap 0–**60** (reusing
  `_significant_niche_tokens` / stemming against the `niche` field), followers
  band 0–**25** (creator-appropriate reason text — never "employees" or
  "distribution/logistics"), country 0–**15**. Every emitted reason cites a
  present, nonblank evidence value; the name-only final fallback and
  `assert_grounded` generalize unchanged.

`ScoreStatus`, `score_batch`, `assert_grounded`, and the "no score without a
grounded citation" guarantees are unchanged and shape-agnostic.

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
- creator `discovery.seed_error` (**warning**).

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
8. **Business-score regression protection:** the Slice 3 anchor-score table
   and business heuristic outputs are unchanged (existing tests re-run green;
   an explicit assertion pins a business anchor).
9. **Tenant isolation:** creator targets, audit rows, and drafts never cross
   workspaces (scoped query checks, as in Slice 2/4).
10. **Sanitized audit details:** no test fixture or asserted audit/banner
    string contains a key, a credential-bearing URL, or a raw provider payload;
    an injected fake key inside a provider error is redacted before audit.
11. **Zero-key demo (integration-style, mocked/seed):** creator campaign →
    seed discovery → creator scoring → draft → approve → pipeline completes.

### 7.2 Live error-shape verification (deletable script, §14.1 pattern)

A temporary, DB-write-free script confirms the §5.4 Apify and YouTube
status mappings against the real APIs before the mapping is relied upon, then
is deleted (collaboration.md rule 11 — not converted to a maintained test,
since it requires live keys). Until it runs, §5.4 stays marked as assumptions.

### 7.3 Live happy-path (only if the owner provides keys)

If the owner pastes a `youtube` and/or `apify` key into a workspace via
Settings (never duplicated into SQLite), verify one live creator campaign
end to end. Otherwise verification is seed + mocked, which is honest but not a
live end-to-end — recorded as a limitation.

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

**This commit** touches only `docs/plans/SLICE_5_PLAN.md`, `collaboration.md`,
and `docs/history/COLLABORATION_LOG.md`.

---

## 9. Remaining assumptions requiring live verification

- Apify and YouTube HTTP-status → typed-status mappings (§5.4) are assumptions
  until the §7.2 script confirms them live (only Apollo's were confirmed in
  Slice 2).
- Provider pricing (§4.3) and the YouTube quota model (§4.4) are current as of
  2026-07-31 and provider-controlled; re-verify before relying on a figure.
- Exact Apify output field names (e.g. TikTok `fans` vs `followers`) are taken
  from the official schemas/READMEs and should be confirmed against a real
  dataset item during implementation; the normalizer must tolerate a missing
  field (→ `None`) rather than raise.
- Live creator end-to-end (§7.3) depends on the owner providing a free YouTube
  and/or Apify key; absent that, verification is seed + mocked.
