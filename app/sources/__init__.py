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

Creator routing (SLICE_5_PLAN.md decision 1) is a deterministic priority,
never an aggregation: Apify when configured, else YouTube when configured,
else creator seed. Business routing (Apollo-or-seed) is unchanged.
"""

from app.models import Brief, Candidate
from app.sources.apify import ApifySource
from app.sources.apify import normalize_evidence as _apify_evidence
from app.sources.apollo import ApolloSource
from app.sources.apollo import normalize_evidence as _apollo_evidence
from app.sources.base import SourceResult, SourceStatus
from app.sources.seed import SeedSource
from app.sources.seed import normalize_creator_evidence as _seed_creator_evidence
from app.sources.seed import normalize_evidence as _seed_business_evidence
from app.sources.youtube import YouTubeSource
from app.sources.youtube import normalize_evidence as _youtube_evidence

# Maps a SourceResult.source_used name to that source's normalize_evidence
# function. Fit-scoring (Slice 3) calls evidence_for() rather than holding a
# live Source object past discover() — each source still owns its own
# normalization. Seed serves both business and creator rows under the same
# source_used == "seed", so its entry is dispatched a second time by
# target_type (SLICE_5_PLAN.md §6.2) rather than colliding on one shape.
_EVIDENCE_NORMALIZERS = {
    "apollo": _apollo_evidence,
    "youtube": _youtube_evidence,
    "apify": _apify_evidence,
    "seed": {"business": _seed_business_evidence, "creator": _seed_creator_evidence},
}


def evidence_for(source_used: str, target_type: str, candidate: Candidate) -> dict:
    """Return normalized, source-neutral evidence for one discovered candidate."""
    normalize = _EVIDENCE_NORMALIZERS[source_used]
    if isinstance(normalize, dict):
        normalize = normalize[target_type]
    return normalize(candidate.raw)


def discover(brief: Brief, settings: dict[str, str]) -> SourceResult:
    if brief.target_type == "creator":
        return _discover_creator(brief, settings)
    return _discover_business(brief, settings)


def _discover_business(brief: Brief, settings: dict[str, str]) -> SourceResult:
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


def _discover_creator(brief: Brief, settings: dict[str, str]) -> SourceResult:
    """Deterministic priority (SLICE_5_PLAN.md §5.1): Apify when configured,
    else YouTube when configured, else creator seed. Never both live sources
    in one campaign — each is tried exactly once, and PARTIAL_RESULTS (an
    Apify sub-source failure) is still a success worth keeping, not a
    trigger to fall back."""
    apify_key = settings.get("apify")
    if apify_key:
        result = ApifySource(apify_key).search(brief)
        if result.status in (SourceStatus.OK, SourceStatus.PARTIAL_RESULTS):
            return result
        return _fallback_to_creator_seed(brief, "apify", result.status, result.reason)

    youtube_key = settings.get("youtube")
    if youtube_key:
        result = YouTubeSource(youtube_key).search(brief)
        if result.status == SourceStatus.OK:
            return result
        return _fallback_to_creator_seed(brief, "youtube", result.status, result.reason)

    # No creator key at all — YouTube is the nominal attempted source
    # (free, keyless-would-be-default in spirit) for a truthful "no key" banner.
    return _fallback_to_creator_seed(brief, "youtube", SourceStatus.NO_KEY, None)


def _fallback_to_creator_seed(
    brief: Brief,
    source_attempted: str,
    primary_status: SourceStatus,
    primary_reason: str | None,
) -> SourceResult:
    """Mirrors _fallback_to_seed for creator campaigns: preserves the real
    live-source status/reason, and only reports SEED_ERROR (no candidates)
    if the creator seed itself fails to load."""
    seed = SeedSource("creator").search(brief)
    if seed.status == SourceStatus.OK:
        return SourceResult(
            seed.candidates,
            primary_status,
            source_attempted=source_attempted,
            source_used="seed",
            reason=primary_reason,
        )

    return SourceResult(
        [],
        SourceStatus.SEED_ERROR,
        source_attempted=source_attempted,
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
    return f"{primary_reason}; and the seed fallback also failed: {seed_part}"[:400]
