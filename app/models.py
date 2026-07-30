"""Pydantic schemas for structured data and model outputs.

Every model call that returns data validates against a schema here, per the
structured-output non-negotiable in CLAUDE.md.
"""

from typing import Literal

from pydantic import BaseModel, Field

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
