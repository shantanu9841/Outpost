"""YouTube Data API v3 creator search, behind the Source interface.

Calls YouTube's REST API directly with the workspace's own pasted key
(BYO-key non-negotiable): a search.list channel query, then one batched
channels.list enrichment call for subscriberCount/country. The key is sent
in the X-goog-api-key request header, never the key= query parameter, so no
request URL is ever credential-bearing (SLICE_5_PLAN.md §4.4). Never raises
past this module's boundary: every outcome, including a malformed 200
payload, comes back as a typed SourceResult.

Live YouTube requires this workspace key (decision 5, SLICE_5_PLAN.md §1) —
there is no keyless discovery and no env-var fallback; discover() only
constructs this class when a workspace key is present.
"""

import httpx
from pydantic import ValidationError

from app.models import Brief, Candidate
from app.sources.base import Source, SourceResult, SourceStatus, canonical_name, coerce_int

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

# Named constants (SLICE_5_PLAN.md §4.0's "easy for the owner to adjust"
# discipline, applied here too): a strict per-request timeout, independent
# of anything provider-side, and how many channels to discover per search.
REQUEST_TIMEOUT_SECS = 30
MAX_RESULTS = 10


def _error_detail(response: httpx.Response) -> tuple[str | None, str | None]:
    """Best-effort (message, reason_code) from a YouTube error body.

    reason_code is the first structured errors[0].reason (e.g. "keyInvalid",
    "quotaExceeded") YouTube's v3 error shape carries alongside the HTTP
    status. Returns (None, None) on any non-dict/malformed body rather than
    raising — classification always has a safe default (PROVIDER_ERROR).
    """
    try:
        body = response.json()
    except (ValueError, TypeError):
        return None, None
    if not isinstance(body, dict):
        return None, None
    error = body.get("error")
    if not isinstance(error, dict):
        return None, None
    message = error.get("message")
    message = message if isinstance(message, str) else None
    reason_code = None
    errors = error.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        reason = errors[0].get("reason")
        reason_code = reason if isinstance(reason, str) else None
    return message, reason_code


def _safe_reason(response: httpx.Response, api_key: str) -> str:
    """A sanitized, UI/audit-safe error string. Never the key, headers, or URL."""
    message, _ = _error_detail(response)
    if message and message.strip():
        return message.replace(api_key, "[REDACTED]")[:300]
    return f"YouTube returned HTTP {response.status_code}"


def normalize_evidence(raw: dict) -> dict:
    """Map YouTube's channel fields to the source-neutral creator evidence
    shape (SLICE_5_PLAN.md §6.1). "name" goes through canonical_name() on
    the same raw title _to_candidate uses, so the two can never diverge.
    """
    return {
        "name": canonical_name(raw.get("title")),
        "niche": raw.get("description"),
        "followers": coerce_int(raw.get("subscriberCount")),
        "country": raw.get("country"),
        "handle": raw.get("channelId"),
        "platform": "youtube",
    }


class YouTubeSource(Source):
    name = "youtube"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, brief: Brief) -> SourceResult:
        try:
            search_resp = httpx.get(
                SEARCH_URL,
                headers={"X-goog-api-key": self.api_key},
                params={
                    "part": "snippet",
                    "type": "channel",
                    "q": brief.niche_or_industry,
                    "maxResults": MAX_RESULTS,
                },
                timeout=REQUEST_TIMEOUT_SECS,
            )
        except httpx.RequestError as exc:
            return self._result(
                [], SourceStatus.NETWORK_ERROR, f"network error ({type(exc).__name__})"
            )

        failure = self._classify(search_resp)
        if failure is not None:
            return self._result([], failure, _safe_reason(search_resp, self.api_key))

        channel_ids = self._extract_channel_ids(search_resp)
        if not channel_ids:
            return self._result([], SourceStatus.OK, None)

        try:
            channels_resp = httpx.get(
                CHANNELS_URL,
                headers={"X-goog-api-key": self.api_key},
                params={"part": "snippet,statistics", "id": ",".join(channel_ids)},
                timeout=REQUEST_TIMEOUT_SECS,
            )
        except httpx.RequestError as exc:
            return self._result(
                [], SourceStatus.NETWORK_ERROR, f"network error ({type(exc).__name__})"
            )

        failure = self._classify(channels_resp)
        if failure is not None:
            return self._result([], failure, _safe_reason(channels_resp, self.api_key))

        return self._parse_channels(channels_resp)

    def _classify(self, response: httpx.Response) -> SourceStatus | None:
        """A failure SourceStatus, or None when the 200 body still needs parsing.

        Mapping per SLICE_5_PLAN.md §5.4, confirmed live for the
        invalid-key case (2026-07-31): 400 with an "API key not valid"
        message, or 403 reason "keyInvalid" -> INVALID_KEY; 403 reason
        "quotaExceeded"/"rateLimitExceeded" -> RATE_LIMITED; anything else
        non-200 -> PROVIDER_ERROR (never a credential rejection).
        """
        if response.status_code == 200:
            return None
        message, reason_code = _error_detail(response)
        if response.status_code == 400 and message and "api key not valid" in message.lower():
            return SourceStatus.INVALID_KEY
        if response.status_code == 403 and reason_code == "keyInvalid":
            return SourceStatus.INVALID_KEY
        if response.status_code == 403 and reason_code in ("quotaExceeded", "rateLimitExceeded"):
            return SourceStatus.RATE_LIMITED
        return SourceStatus.PROVIDER_ERROR

    @staticmethod
    def _extract_channel_ids(response: httpx.Response) -> list[str]:
        try:
            body = response.json()
        except (ValueError, TypeError):
            return []
        items = body.get("items") if isinstance(body, dict) else None
        if not isinstance(items, list):
            return []
        ids = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            channel_id = item_id.get("channelId") if isinstance(item_id, dict) else None
            if isinstance(channel_id, str) and channel_id:
                ids.append(channel_id)
        return ids

    def _parse_channels(self, response: httpx.Response) -> SourceResult:
        """Turn a channels.list 200 into candidates, or a typed PROVIDER_ERROR
        if malformed — mirrors ApolloSource._parse_ok's discipline."""
        try:
            body = response.json()
            items = body.get("items", []) if isinstance(body, dict) else None
            if not isinstance(items, list):
                raise ValueError("YouTube channels response had no items list")
            candidates = [self._to_candidate(item) for item in items]
        except (ValueError, TypeError, KeyError, ValidationError):
            return self._result(
                [], SourceStatus.PROVIDER_ERROR, "YouTube returned an unexpected response payload"
            )
        return self._result(candidates, SourceStatus.OK, None)

    def _result(self, candidates, status, reason) -> SourceResult:
        return SourceResult(candidates, status, "youtube", "youtube", reason)

    def evidence(self, candidate: Candidate) -> dict:
        return normalize_evidence(candidate.raw)

    @staticmethod
    def _to_candidate(item: dict) -> Candidate:
        if not isinstance(item, dict):
            raise ValueError("channel row was not an object")
        snippet = item.get("snippet") or {}
        statistics = item.get("statistics") or {}
        channel_id = item.get("id")
        channel_id = channel_id if isinstance(channel_id, str) else None
        title = snippet.get("title")
        country = snippet.get("country")

        # Controlled provenance marker (SLICE_5_PLAN.md §6.1), never copied
        # from an untrusted provider field — set from this source's own
        # constant so an Apify batch's per-actor markers can't collide with
        # it and campaign_detail can render "YouTube" without inspecting
        # target.source (which stays the source-level "youtube" value).
        raw = {
            "title": title,
            "description": snippet.get("description"),
            "subscriberCount": statistics.get("subscriberCount"),
            "country": country,
            "channelId": channel_id,
            "_outpost_platform": "youtube",
        }
        return Candidate(
            source="youtube",
            external_id=channel_id,
            name=canonical_name(title),
            handle_or_domain=channel_id,
            reach=coerce_int(statistics.get("subscriberCount")),
            location=country if isinstance(country, str) else None,
            raw=raw,
        )
