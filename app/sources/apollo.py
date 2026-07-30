"""Apollo company search, behind the Source interface.

Calls Apollo's REST API directly with the workspace's own pasted key
(BYO-key non-negotiable) — never the builder's own Apollo account. Never
raises past this module's boundary: every outcome, success or failure —
including a malformed HTTP 200 payload — comes back as a typed SourceResult
so discover() can apply one uniform fallback policy.

HTTP status classification is source-agnostic and deliberately does not treat
every non-200 as a credential problem: only 401 is a rejected key. A 403 is a
plan restriction, a 429 is throttling, and 5xx/422/anything-unexpected is a
provider-side failure — none of which should tell the owner to replace a
working key.
"""

import httpx
from pydantic import ValidationError

from app.models import Brief, Candidate
from app.sources.base import Source, SourceResult, SourceStatus

SEARCH_URL = "https://api.apollo.io/api/v1/mixed_companies/search"


def _safe_reason(response: httpx.Response, api_key: str) -> str:
    """A sanitized, UI/audit-safe error string.

    Never returns a raw provider payload: only a genuine string message from a
    known field, otherwise a generic HTTP-status message. Never includes the
    key, headers, or URL.
    """
    try:
        body = response.json()
    except (ValueError, TypeError):
        return f"Apollo returned HTTP {response.status_code}"
    if isinstance(body, dict):
        for field in ("error", "message"):
            value = body.get(field)
            if isinstance(value, str) and value.strip():
                return value.replace(api_key, "[REDACTED]")[:300]
    return f"Apollo returned HTTP {response.status_code}"


def normalize_evidence(raw: dict) -> dict:
    """Map Apollo's field names to the source-neutral evidence shape.

    Fit-scoring (app/agent/scoring.py) reads only this shape, never Apollo's
    own field names — so evidence reads identically regardless of which
    source produced the target.
    """
    return {
        "name": raw.get("name"),
        "industry": raw.get("industry"),
        "employees": raw.get("estimated_num_employees"),
        "country": raw.get("country"),
        "domain": raw.get("primary_domain") or raw.get("website_url"),
    }


class ApolloSource(Source):
    name = "apollo"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, brief: Brief) -> SourceResult:
        keywords = [brief.niche_or_industry, "distributor", "logistics"]
        body = {
            "q_organization_keyword_tags": keywords,
            "organization_locations": brief.target_countries,
            "page": 1,
            "per_page": 25,
        }
        try:
            response = httpx.post(
                SEARCH_URL,
                headers={"X-Api-Key": self.api_key},
                json=body,
                timeout=30,
            )
        except httpx.RequestError as exc:
            # Do not interpolate str(exc): keep the reason free of any URL.
            return self._result(
                [], SourceStatus.NETWORK_ERROR, f"network error ({type(exc).__name__})"
            )

        status = response.status_code
        if status == 200:
            return self._parse_ok(response)
        if status == 401:
            return self._result([], SourceStatus.INVALID_KEY, _safe_reason(response, self.api_key))
        if status == 403:
            return self._result(
                [], SourceStatus.INSUFFICIENT_PLAN, _safe_reason(response, self.api_key)
            )
        if status == 429:
            return self._result([], SourceStatus.RATE_LIMITED, _safe_reason(response, self.api_key))
        # 5xx, 422, and any other unexpected non-200 are provider-side failures,
        # never a credential rejection.
        return self._result([], SourceStatus.PROVIDER_ERROR, _safe_reason(response, self.api_key))

    def _parse_ok(self, response: httpx.Response) -> SourceResult:
        """Turn a 200 into candidates, or a typed PROVIDER_ERROR if malformed."""
        try:
            payload = response.json()
            organizations = payload.get("organizations", []) if isinstance(payload, dict) else None
            if not isinstance(organizations, list):
                raise ValueError("Apollo 200 payload had no organizations list")
            candidates = [self._to_candidate(org) for org in organizations]
        except (ValueError, TypeError, KeyError, ValidationError):
            return self._result(
                [], SourceStatus.PROVIDER_ERROR, "Apollo returned an unexpected response payload"
            )
        return self._result(candidates, SourceStatus.OK, None)

    def _result(self, candidates, status, reason) -> SourceResult:
        return SourceResult(candidates, status, "apollo", "apollo", reason)

    def evidence(self, candidate: Candidate) -> dict:
        # Fit-scoring (Slice 3) reads a normalized shape, not Apollo's raw
        # field names, so scoring never has to know per-provider conventions.
        return normalize_evidence(candidate.raw)

    @staticmethod
    def _to_candidate(org: dict) -> Candidate:
        if not isinstance(org, dict):
            raise ValueError("organization row was not an object")
        location = ", ".join(
            part
            for part in (org.get("city"), org.get("state"), org.get("country"))
            if part
        ) or None

        return Candidate(
            source="apollo",
            external_id=str(org.get("id")) if org.get("id") else None,
            name=org.get("name", "Unknown company"),
            handle_or_domain=org.get("primary_domain") or org.get("website_url"),
            reach=org.get("estimated_num_employees"),
            location=location,
            raw=org,
        )
