"""The Source interface every discovery provider implements.

Adding or swapping a source is a config change (which class discover() picks),
not a rewrite, per the source-agnostic non-negotiable. Every source's
search() returns the same SourceResult contract, so discover() can apply one
uniform fallback policy regardless of which source ran.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from app.models import Brief, Candidate


class SourceStatus(str, Enum):
    OK = "ok"
    NO_KEY = "no_key"
    INVALID_KEY = "invalid_key"          # credential rejected (e.g. Apollo 401)
    INSUFFICIENT_PLAN = "insufficient_plan"  # valid key, plan lacks the endpoint (403)
    RATE_LIMITED = "rate_limited"        # provider is throttling (429) — not a key problem
    PROVIDER_ERROR = "provider_error"    # provider-side failure (5xx/422/unexpected) — not a key problem
    NETWORK_ERROR = "network_error"      # could not reach the provider at all
    SEED_ERROR = "seed_error"            # the local seed fallback itself could not load


def coerce_int(value: object) -> int | None:
    """Best-effort int coercion for a normalized evidence field.

    Provider payloads can return a numeric-looking field as a string (or
    some other unexpected type); scoring's heuristic does arithmetic
    comparisons on evidence["employees"], so a value that can't be safely
    read as an int becomes None (evidence treats it as unavailable) rather
    than raising deep inside scoring.

    A float is only accepted when it is finite and integral (e.g. 180.0):
    NaN and +-infinity are not real counts, and int(nan)/int(inf) both raise
    in plain Python, which would break this function's own "never raises"
    contract. A non-integral float (e.g. 180.5) is not silently truncated —
    guessing at a fractional employee count would misrepresent the evidence,
    so it becomes None like any other value that can't be read as an int.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or value != int(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


DEFAULT_NAME = "Unknown company"


def canonical_name(raw_name: object, fallback: str = DEFAULT_NAME) -> str:
    """One canonical, nonblank name for a source's evidence and candidate.

    A source that calls this once for Candidate.name and once (on the same
    underlying value) for its normalized evidence's "name" field can never
    have the two diverge: missing, None, an empty string, and a
    whitespace-only string all become the same fallback. Before this helper
    existed, Apollo used two subtly different fallback expressions for the
    same value (`.get(k, default)` vs `.get(k) or default`), which treated a
    present-but-blank name differently in each place.
    """
    if isinstance(raw_name, str):
        stripped = raw_name.strip()
        if stripped:
            return stripped
    return fallback


@dataclass
class SourceResult:
    candidates: list[Candidate]
    status: SourceStatus
    source_attempted: str  # the source discovery meant to use, e.g. "apollo"
    source_used: str  # the source that actually produced these candidates
    reason: str | None  # human-readable, sanitized, safe for UI/audit


class Source(ABC):
    name: str

    @abstractmethod
    def search(self, brief: Brief) -> SourceResult:
        """Return candidate targets matching this brief. Never raises."""

    @abstractmethod
    def evidence(self, candidate: Candidate) -> dict:
        """Return an evidence blob for one candidate, used by fit-scoring (Slice 3)."""
