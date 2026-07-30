"""Discovery orchestration: picks a source and owns fallback semantics.

discover() is the only place that knows *why* seed data was used — individual
sources don't know they're a fallback. It always returns exactly one
SourceResult, never raises, and — on a failed live source — preserves that
source's own status and sanitized reason so the UI can show both the
fallback data and why the fallback happened.
"""

from app.models import Brief
from app.sources.apollo import ApolloSource
from app.sources.base import SourceResult, SourceStatus
from app.sources.seed import SeedSource


def discover(brief: Brief, settings: dict[str, str]) -> SourceResult:
    if brief.target_type != "business":
        # Creator sources arrive in Slice 5.
        seed = SeedSource("creator").search(brief)
        return SourceResult(
            seed.candidates,
            SourceStatus.NO_KEY,
            source_attempted="youtube",
            source_used="seed",
            reason="Creator sources arrive in Slice 5",
        )

    apollo_key = settings.get("apollo")
    if not apollo_key:
        seed = SeedSource("business").search(brief)
        return SourceResult(
            seed.candidates, SourceStatus.NO_KEY, source_attempted="apollo", source_used="seed", reason=None
        )

    apollo_result = ApolloSource(apollo_key).search(brief)
    if apollo_result.status == SourceStatus.OK:
        return apollo_result  # source_attempted == source_used == "apollo"

    # Apollo failed without raising; fall back to seed, but preserve why.
    seed = SeedSource("business").search(brief)
    return SourceResult(
        seed.candidates,
        apollo_result.status,
        source_attempted="apollo",
        source_used="seed",
        reason=apollo_result.reason,
    )
