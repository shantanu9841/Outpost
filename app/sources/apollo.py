"""Apollo company search, behind the Source interface.

Calls Apollo's REST API directly with the workspace's own pasted key
(BYO-key non-negotiable) — never the builder's own Apollo account. Never
raises past this module's boundary: every outcome, success or failure, comes
back as a SourceResult so discover() can apply one uniform fallback policy.
"""

import httpx

from app.models import Brief, Candidate
from app.sources.base import Source, SourceResult, SourceStatus

SEARCH_URL = "https://api.apollo.io/api/v1/mixed_companies/search"


def _safe_reason(response: httpx.Response) -> str:
    """A sanitized, UI/audit-safe error string — never the key, url, or headers."""
    try:
        message = response.json()["error"]
        return str(message)[:300]
    except (KeyError, TypeError, ValueError):
        return f"Apollo returned HTTP {response.status_code}"


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
            return SourceResult([], SourceStatus.NETWORK_ERROR, "apollo", "apollo", str(exc)[:300])

        if response.status_code == 200:
            organizations = response.json().get("organizations", [])
            candidates = [self._to_candidate(org) for org in organizations]
            return SourceResult(candidates, SourceStatus.OK, "apollo", "apollo", None)

        if response.status_code == 401:
            return SourceResult([], SourceStatus.INVALID_KEY, "apollo", "apollo", _safe_reason(response))

        if response.status_code == 403:
            return SourceResult(
                [], SourceStatus.INSUFFICIENT_PLAN, "apollo", "apollo", _safe_reason(response)
            )

        return SourceResult([], SourceStatus.INVALID_KEY, "apollo", "apollo", _safe_reason(response))

    def evidence(self, candidate: Candidate) -> dict:
        # Fit-scoring (Slice 3) reads the firmographics already captured on search.
        return candidate.raw

    @staticmethod
    def _to_candidate(org: dict) -> Candidate:
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
