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


def validate_draft_body(text: str) -> str:
    """Shared length bound for both a model-authored and a human-submitted
    draft body. Raises ValueError on failure; callers translate that into
    the error shape appropriate to their layer (a Pydantic ValidationError
    here, db.InvalidDraftBody in app/db.py).

    Lives here, not in app/agent/drafting.py, because OutreachDraft (below)
    needs to call it from its own field validator in this same module — a
    models -> drafting -> models import cycle. drafting.py never imports
    this: every OutreachDraft it builds, LLM or heuristic, is already
    validated by the schema below at construction time.

    Normalizes CRLF/CR to LF before anything else. An HTML <textarea>
    submits with \\r\\n line endings regardless of how the value was set
    (HTML spec), while a stored draft body uses plain \\n — without this,
    approve_draft's exact-match "did the human edit this" comparison would
    call every unedited approval an edit, since the two never compared
    equal (caught by manual browser verification, not the TestClient-based
    tests, which post form data directly and never exercise a real
    textarea's line-ending normalization).
    """
    stripped = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(stripped) < 20:
        raise ValueError("draft body is too short to be a real message")
    if len(stripped) > 1500:
        raise ValueError("draft body is too long for an outreach message")
    return stripped


class OutreachDraft(BaseModel):
    """A drafted outreach message, plus the one evidence pair it cites.

    The evidence pair is validation metadata: app/agent/drafting.py's
    grounding gate checks it against the target's stored, already-verified
    Slice 3 fit reasons before trusting the body. It is not persisted as a
    draft-table column.
    """

    body: str
    evidence_key: str
    evidence_value: str

    @field_validator("evidence_key", "evidence_value")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("evidence_key and evidence_value are required")
        return v

    @field_validator("body")
    @classmethod
    def body_is_reasonable(cls, v: str) -> str:
        return validate_draft_body(v)
