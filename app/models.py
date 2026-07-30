"""Pydantic schemas for structured data and model outputs.

Every model call that returns data validates against a schema here, per the
structured-output non-negotiable in CLAUDE.md.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TargetType = Literal["creator", "business"]


class Brief(BaseModel):
    """A parsed, validated version of "what are you promoting"."""

    product: str
    audience: str
    tone: str
    target_type: TargetType
    niche_or_industry: str
    target_countries: list[str] = Field(default_factory=lambda: ["United States"])


class Candidate(BaseModel):
    """The normalized shape every Source returns, regardless of provider."""

    source: str  # apollo, seed, youtube, apify
    external_id: str | None = None
    name: str
    handle_or_domain: str | None = None
    reach: int | None = None  # employees for businesses, subscribers for creators
    location: str | None = None
    raw: dict = Field(default_factory=dict)


class FitReason(BaseModel):
    """One cited reason contributing to a fit score.

    A citation is a claim, not just a non-empty string: evidence_key/value must
    later be checked against the actual evidence (see app/agent/scoring.py's
    _is_grounded) before a score is ever stored. The schema only guarantees
    shape (non-blank fields); it cannot see the runtime evidence to guarantee
    truth.
    """

    reason: str
    evidence_key: str
    evidence_value: str

    @field_validator("reason", "evidence_key", "evidence_value")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason, evidence_key, and evidence_value are all required")
        return v


class FitAssessment(BaseModel):
    """One target's fit score and its cited reasons, within a FitBatch."""

    target_index: int
    fit_score: int
    reasons: list[FitReason]

    @field_validator("fit_score")
    @classmethod
    def in_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("fit_score must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def at_least_one_reason(self) -> "FitAssessment":
        if not self.reasons:
            raise ValueError("a fit score requires at least one cited reason")
        return self


class FitBatch(BaseModel):
    """One structured response scoring every discovered target at once."""

    assessments: list[FitAssessment]
