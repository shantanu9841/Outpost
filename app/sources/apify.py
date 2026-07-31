"""Apify creator search (Instagram + TikTok), behind the Source interface.

Runs two actors — apify/instagram-scraper and clockworks/tiktok-scraper —
with the workspace's own pasted Apify token (BYO-key non-negotiable) and
merges their normalized candidates (SLICE_5_PLAN.md decision 2). Never
raises past this module's boundary: every failure at any stage (start,
poll, fetch, or a malformed item) becomes a typed sub-status/reason pair
that search() folds into one SourceResult, honest about which platform (if
any) failed and why (§5.3).

Transport: Authorization: Bearer header only, never a token query parameter
(§4.0). Uses Apify's start-run + bounded-poll + fetch sequence — never
run-sync, which holds one connection open for up to 300s — with every run
bounded by an actor-run timeout, a maxItems cap, and a maxTotalChargeUsd
cost ceiling, all named constants below so the owner can adjust them.
"""

import time

import httpx
from pydantic import ValidationError

from app.models import Brief, Candidate
from app.sources.base import Source, SourceResult, SourceStatus, canonical_name, coerce_int

API_BASE = "https://api.apify.com/v2"

# Actor ids (SLICE_5_PLAN.md §4.1/§4.2, verified against apify.com 2026-07-31).
INSTAGRAM_ACTOR_ID = "shu8hvrXbJbY3Eb9W"  # apify/instagram-scraper
TIKTOK_ACTOR_ID = "GdWCkxBtKWOsKjdch"  # clockworks/tiktok-scraper

# Named run-bounding constants (§4.0) — every run's duration, item count,
# and cost are capped here, independent of provider defaults.
RUN_TIMEOUT_SECS = 120  # actor-run duration cap, sent as the start-run ?timeout=
MAX_ITEMS = 10  # ?maxItems= cap, and each actor's own per-search result limit
MAX_TOTAL_CHARGE_USD = 0.10  # ?maxTotalChargeUsd= hard cost ceiling
REQUEST_TIMEOUT_SECS = 30  # per-request httpx timeout, independent of the run
POLL_INTERVAL_SECS = 3
POLL_BUDGET_SECS = 150  # wall-clock cap on the whole poll loop

TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}

# Deterministic precedence when Instagram and TikTok fail with different
# statuses (SLICE_5_PLAN.md §5.3) — most actionable/credential-relevant first.
_STATUS_PRECEDENCE = (
    SourceStatus.INVALID_KEY,
    SourceStatus.INSUFFICIENT_PLAN,
    SourceStatus.RATE_LIMITED,
    SourceStatus.PROVIDER_ERROR,
    SourceStatus.NETWORK_ERROR,
)


class _ApifyRunError(Exception):
    """Internal control-flow signal for one actor run's failure. Caught at
    the _run_actor boundary and turned into a (status, reason) pair — never
    escapes this module."""

    def __init__(self, status: SourceStatus, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _safe_reason(response: httpx.Response, api_key: str) -> str:
    """A sanitized, UI/audit-safe error string. Never the key, headers, or URL."""
    try:
        body = response.json()
    except (ValueError, TypeError):
        return f"Apify returned HTTP {response.status_code}"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.replace(api_key, "[REDACTED]")[:300]
    return f"Apify returned HTTP {response.status_code}"


def _classify_start_status(status_code: int) -> SourceStatus | None:
    """A failure SourceStatus for the start-run call, or None on 2xx
    (the run started and polling should begin). Per §5.4: 401 -> INVALID_KEY;
    402/403 -> INSUFFICIENT_PLAN (out of credit / plan limit); 429 ->
    RATE_LIMITED; any other non-2xx -> PROVIDER_ERROR."""
    if 200 <= status_code < 300:
        return None
    if status_code == 401:
        return SourceStatus.INVALID_KEY
    if status_code in (402, 403):
        return SourceStatus.INSUFFICIENT_PLAN
    if status_code == 429:
        return SourceStatus.RATE_LIMITED
    return SourceStatus.PROVIDER_ERROR


def normalize_evidence(raw: dict) -> dict:
    """Map an Apify creator row (either actor) to the source-neutral creator
    evidence shape (SLICE_5_PLAN.md §6.1). Both actors' per-platform field
    names are already unified onto this same raw-key set by
    _instagram_to_candidate/_tiktok_to_candidate, so one function reads
    correctly for both. "name" goes through canonical_name() on the same
    raw value the candidate itself used, so the two can never diverge.
    """
    return {
        "name": canonical_name(raw.get("name")),
        "niche": raw.get("bio"),
        "followers": coerce_int(raw.get("followers")),
        "country": raw.get("country"),
        "handle": raw.get("handle"),
        "platform": raw.get("_outpost_platform"),
    }


class ApifySource(Source):
    name = "apify"

    def __init__(self, api_key: str, *, sleep=time.sleep, now=time.monotonic):
        self.api_key = api_key
        # Injectable clock/sleep so tests can drive the poll loop without a
        # real 150s wait (SLICE_5_PLAN.md §7.1 item 15); production uses the
        # real time module via the defaults above.
        self._sleep = sleep
        self._now = now

    def search(self, brief: Brief) -> SourceResult:
        ig_candidates, ig_status, ig_reason = self._run_instagram(brief)
        tt_candidates, tt_status, tt_reason = self._run_tiktok(brief)

        ig_ok = ig_status == SourceStatus.OK
        tt_ok = tt_status == SourceStatus.OK

        if ig_ok and tt_ok:
            return SourceResult(ig_candidates + tt_candidates, SourceStatus.OK, "apify", "apify", None)

        if ig_ok or tt_ok:
            ok_candidates = ig_candidates if ig_ok else tt_candidates
            ok_platform = "Instagram" if ig_ok else "TikTok"
            failed_platform = "TikTok" if ig_ok else "Instagram"
            failed_reason = tt_reason if ig_ok else ig_reason
            reason = f"{failed_platform} unavailable ({failed_reason}); showing {ok_platform} only"[:400]
            return SourceResult(ok_candidates, SourceStatus.PARTIAL_RESULTS, "apify", "apify", reason)

        combined_status = self._precedence(ig_status, tt_status)
        combined_reason = f"instagram: {ig_reason}; tiktok: {tt_reason}"[:400]
        return SourceResult([], combined_status, "apify", "apify", combined_reason)

    @staticmethod
    def _precedence(a: SourceStatus, b: SourceStatus) -> SourceStatus:
        for status in _STATUS_PRECEDENCE:
            if a == status or b == status:
                return status
        return a  # both failure statuses are always members of _STATUS_PRECEDENCE

    def _run_instagram(self, brief: Brief) -> tuple[list[Candidate], SourceStatus, str | None]:
        input_body = {
            "resultsType": "details",
            "search": brief.niche_or_industry,
            "searchType": "user",
            "searchLimit": MAX_ITEMS,
        }
        return self._run_actor(INSTAGRAM_ACTOR_ID, input_body, self._instagram_to_candidate)

    def _run_tiktok(self, brief: Brief) -> tuple[list[Candidate], SourceStatus, str | None]:
        input_body = {
            "searchQueries": [brief.niche_or_industry],
            "searchSection": "/user",
            "maxProfilesPerQuery": MAX_ITEMS,
        }
        return self._run_actor(TIKTOK_ACTOR_ID, input_body, self._tiktok_to_candidate)

    def _run_actor(
        self, actor_id: str, input_body: dict, to_candidate
    ) -> tuple[list[Candidate], SourceStatus, str | None]:
        try:
            run = self._start_run(actor_id, input_body)
            items = self._poll_and_fetch(run)
        except _ApifyRunError as exc:
            return [], exc.status, exc.reason

        try:
            candidates = [to_candidate(item) for item in items]
        except (ValueError, TypeError, KeyError, ValidationError):
            return [], SourceStatus.PROVIDER_ERROR, "Apify returned an unexpected item payload"
        return candidates, SourceStatus.OK, None

    def _start_run(self, actor_id: str, input_body: dict) -> dict:
        try:
            response = httpx.post(
                f"{API_BASE}/actors/{actor_id}/runs",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={
                    "timeout": RUN_TIMEOUT_SECS,
                    "maxItems": MAX_ITEMS,
                    "maxTotalChargeUsd": MAX_TOTAL_CHARGE_USD,
                },
                json=input_body,
                timeout=REQUEST_TIMEOUT_SECS,
            )
        except httpx.RequestError as exc:
            raise _ApifyRunError(
                SourceStatus.NETWORK_ERROR, f"network error ({type(exc).__name__})"
            ) from exc

        failure = _classify_start_status(response.status_code)
        if failure is not None:
            raise _ApifyRunError(failure, _safe_reason(response, self.api_key))

        run = self._extract_run(response, "run-start")
        return run

    def _extract_run(self, response: httpx.Response, stage: str) -> dict:
        try:
            body = response.json()
            run = body.get("data") if isinstance(body, dict) else None
            if not isinstance(run, dict):
                raise ValueError(f"Apify {stage} response had no data object")
        except (ValueError, TypeError) as exc:
            raise _ApifyRunError(
                SourceStatus.PROVIDER_ERROR, f"Apify returned an unexpected {stage} payload"
            ) from exc
        return run

    def _poll_and_fetch(self, run: dict) -> list:
        run_id = run.get("id")
        if not isinstance(run_id, str) or not run_id:
            raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, "Apify run had no id")

        status = run.get("status")
        dataset_id = run.get("defaultDatasetId")
        deadline = self._now() + POLL_BUDGET_SECS

        while status not in TERMINAL_RUN_STATUSES:
            remaining = deadline - self._now()
            if remaining <= 0:
                raise _ApifyRunError(
                    SourceStatus.PROVIDER_ERROR, "Apify run polling exceeded its wall-clock budget"
                )
            self._sleep(min(POLL_INTERVAL_SECS, remaining))

            # Sleeping can consume the final fraction of the budget. Recheck
            # before opening another connection, and give httpx no more than
            # the time actually left rather than a fresh 30-second allowance.
            remaining = deadline - self._now()
            if remaining <= 0:
                raise _ApifyRunError(
                    SourceStatus.PROVIDER_ERROR, "Apify run polling exceeded its wall-clock budget"
                )
            try:
                response = httpx.get(
                    f"{API_BASE}/actor-runs/{run_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=min(REQUEST_TIMEOUT_SECS, remaining),
                )
            except httpx.RequestError as exc:
                raise _ApifyRunError(
                    SourceStatus.NETWORK_ERROR, f"network error while polling ({type(exc).__name__})"
                ) from exc
            if self._now() > deadline:
                raise _ApifyRunError(
                    SourceStatus.PROVIDER_ERROR, "Apify run polling exceeded its wall-clock budget"
                )
            if response.status_code != 200:
                raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, _safe_reason(response, self.api_key))
            run = self._extract_run(response, "poll")
            status = run.get("status")
            dataset_id = run.get("defaultDatasetId") or dataset_id

        if status != "SUCCEEDED":
            raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, f"Apify run ended in status {status}")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, "Apify run succeeded with no dataset id")

        try:
            response = httpx.get(
                f"{API_BASE}/datasets/{dataset_id}/items",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=REQUEST_TIMEOUT_SECS,
            )
        except httpx.RequestError as exc:
            raise _ApifyRunError(
                SourceStatus.NETWORK_ERROR, f"network error while fetching results ({type(exc).__name__})"
            ) from exc
        if response.status_code != 200:
            raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, _safe_reason(response, self.api_key))

        try:
            items = response.json()
        except (ValueError, TypeError) as exc:
            raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, "Apify dataset items were not valid JSON") from exc
        if not isinstance(items, list):
            raise _ApifyRunError(SourceStatus.PROVIDER_ERROR, "Apify dataset items were not a list")
        return items

    def evidence(self, candidate: Candidate) -> dict:
        return normalize_evidence(candidate.raw)

    @staticmethod
    def _instagram_to_candidate(item: dict) -> Candidate:
        if not isinstance(item, dict):
            raise ValueError("Instagram result row was not an object")
        name = item.get("fullName")
        username = item.get("username")
        username = username if isinstance(username, str) else None
        raw = {
            "name": name,
            "bio": item.get("biography"),
            "followers": item.get("followersCount"),
            "country": None,  # generally absent for Instagram profiles
            "handle": username,
            "_outpost_platform": "instagram",
        }
        return Candidate(
            source="apify",
            external_id=username,
            name=canonical_name(name or username, fallback="Unknown creator"),
            handle_or_domain=username,
            reach=coerce_int(item.get("followersCount")),
            location=None,
            raw=raw,
        )

    @staticmethod
    def _tiktok_to_candidate(item: dict) -> Candidate:
        if not isinstance(item, dict):
            raise ValueError("TikTok result row was not an object")

        # Current clockworks/tiktok-scraper datasets place profile metadata in
        # authorMeta. Keep the documented legacy flat aliases as a defensive
        # compatibility path, but never accept a row with no creator metadata
        # at all — that would silently persist an "unknown" paid result.
        author_meta = item.get("authorMeta")
        if author_meta is not None and not isinstance(author_meta, dict):
            raise ValueError("TikTok author metadata was not an object")
        profile = author_meta if isinstance(author_meta, dict) else item
        if not any(
            key in profile
            for key in ("id", "name", "nickName", "nickname", "uniqueId", "username", "handle")
        ):
            raise ValueError("TikTok result row had no creator metadata")

        if author_meta is not None:
            # In authorMeta, name is the username/handle and nickName is the
            # display name. Prefer the human-readable name for presentation.
            handle = profile.get("name") or profile.get("uniqueId") or profile.get("username")
            name = profile.get("nickName") or profile.get("nickname") or handle
        else:
            name = profile.get("nickname") or profile.get("nickName") or profile.get("name")
            handle = profile.get("uniqueId") or profile.get("username") or profile.get("handle")
        handle = handle if isinstance(handle, str) else None
        followers = profile.get("fans")
        if followers is None:
            followers = profile.get("followers")
        country = profile.get("region") or profile.get("country")
        country = country if isinstance(country, str) else None
        external_id = profile.get("id")
        external_id = external_id if isinstance(external_id, str) else handle
        raw = {
            "name": name,
            "bio": profile.get("signature") or profile.get("bio"),
            "followers": followers,
            "country": country,
            "handle": handle,
            "_outpost_platform": "tiktok",
        }
        return Candidate(
            source="apify",
            external_id=external_id,
            name=canonical_name(name or handle, fallback="Unknown creator"),
            handle_or_domain=handle,
            reach=coerce_int(followers),
            location=country,
            raw=raw,
        )
