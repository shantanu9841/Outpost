"""Discovery orchestration: picks a source and owns fallback semantics.

discover() is the only place that knows *why* seed data was used — individual
sources don't know they're a fallback. It always returns exactly one
SourceResult, never raises, and on a failed live source preserves that
source's own status and sanitized reason so the UI can show both the fallback
data and why the fallback happened.

If the seed fallback *itself* fails to load, discover() does not pretend seed
data was shown: it returns SEED_ERROR with an explanation that names both the
original live-source problem (if any) and the seed failure, and an empty
candidate list.
"""

from app.models import Brief, Candidate
from app.sources.apollo import ApolloSource
from app.sources.apollo import normalize_evidence as _apollo_evidence
from app.sources.base import SourceResult, SourceStatus
from app.sources.seed import SeedSource
from app.sources.seed import normalize_evidence as _seed_evidence

# Maps a SourceResult.source_used name to that source's normalize_evidence
# function. Fit-scoring (Slice 3) calls evidence_for() rather than holding a
# live Source object past discover() — each source still owns its own
# normalization, so Slice 5's creator sources plug in the same way.
_EVIDENCE_NORMALIZERS = {
    "apollo": _apollo_evidence,
    "seed": _seed_evidence,
}


def evidence_for(source_used: str, candidate: Candidate) -> dict:
    """Return normalized, source-neutral evidence for one discovered candidate."""
    normalize = _EVIDENCE_NORMALIZERS[source_used]
    return normalize(candidate.raw)


def discover(brief: Brief, settings: dict[str, str]) -> SourceResult:
    if brief.target_type != "business":
        # Creator sources arrive in Slice 5; seed("creator") returns an empty OK.
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
        return _fallback_to_seed(brief, primary_status=SourceStatus.NO_KEY, primary_reason=None)

    apollo_result = ApolloSource(apollo_key).search(brief)
    if apollo_result.status == SourceStatus.OK:
        return apollo_result  # source_attempted == source_used == "apollo"

    # Apollo failed without raising; fall back to seed, preserving why.
    return _fallback_to_seed(
        brief, primary_status=apollo_result.status, primary_reason=apollo_result.reason
    )


def _fallback_to_seed(
    brief: Brief, primary_status: SourceStatus, primary_reason: str | None
) -> SourceResult:
    """Serve seed data, tagged with why we fell back — unless seed itself fails.

    When seed loads, the returned status/reason is the *primary* (live-source)
    reason, so the banner explains the real cause. When seed does NOT load, the
    result is SEED_ERROR with no candidates, so nothing falsely claims that
    sample data is on screen.
    """
    seed = SeedSource("business").search(brief)
    if seed.status == SourceStatus.OK:
        return SourceResult(
            seed.candidates,
            primary_status,
            source_attempted="apollo",
            source_used="seed",
            reason=primary_reason,
        )

    return SourceResult(
        [],
        SourceStatus.SEED_ERROR,
        source_attempted="apollo",
        source_used="seed",
        reason=_combine_reason(primary_status, primary_reason, seed.reason),
    )


def _combine_reason(
    primary_status: SourceStatus, primary_reason: str | None, seed_reason: str | None
) -> str:
    """A sanitized explanation of both the live-source and seed-load problems."""
    seed_part = seed_reason or "seed data could not be loaded"
    # NO_KEY has no meaningful live-source reason; seed was the primary source.
    if primary_status == SourceStatus.NO_KEY or not primary_reason:
        return seed_part[:300]
    return f"Apollo: {primary_reason}; and the seed fallback also failed: {seed_part}"[:400]
