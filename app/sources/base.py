"""The Source interface every discovery provider implements.

Adding or swapping a source is a config change (which class discover() picks),
not a rewrite, per the source-agnostic non-negotiable. Every source's
search() returns the same SourceResult contract, so discover() can apply one
uniform fallback policy regardless of which source ran.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from app.models import Brief, Candidate


class SourceStatus(str, Enum):
    OK = "ok"
    NO_KEY = "no_key"
    INVALID_KEY = "invalid_key"
    INSUFFICIENT_PLAN = "insufficient_plan"
    NETWORK_ERROR = "network_error"


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
