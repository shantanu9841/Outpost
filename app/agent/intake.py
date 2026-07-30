"""Parse "what are you promoting" into a validated Brief.

target_type is chosen explicitly by the user on the intake form, not left to
the model to guess, because discovery routing depends on it being reliable.
Everything else (product, audience, tone, niche, countries) is parsed by the
LLM when a key is available. With no LLM available anywhere, a deterministic
heuristic still returns a valid Brief, so demo mode never blocks on intake.
"""

import re
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from app import llm
from app.models import Brief, TargetType

SYSTEM_PROMPT = (
    "You read a short description of a product or service being promoted for "
    "outreach and extract a structured brief. Respond with a JSON object only."
)


class IntakeStatus(str, Enum):
    LLM_OK = "llm_ok"
    NO_GEMINI_KEY = "no_gemini_key"
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"


@dataclass
class IntakeResult:
    brief: Brief
    status: IntakeStatus
    reason: str | None  # sanitized, safe for UI/audit; None on LLM_OK/NO_GEMINI_KEY


class _ParsedFields(BaseModel):
    """What the model parses. target_type is supplied by the caller, not this."""

    product: str
    audience: str
    tone: str
    niche_or_industry: str
    target_countries: list[str] = Field(default_factory=lambda: ["United States"])


_COUNTRY_ALIASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(united states|usa|u\.s\.a\.|u\.s\.|us)\b", re.IGNORECASE), "United States"),
    (re.compile(r"\b(united kingdom|uk|u\.k\.|britain)\b", re.IGNORECASE), "United Kingdom"),
    (re.compile(r"\b(germany|de)\b", re.IGNORECASE), "Germany"),
]


def _extract_countries(text: str) -> list[str]:
    found = []
    for pattern, canonical in _COUNTRY_ALIASES:
        if pattern.search(text) and canonical not in found:
            found.append(canonical)
    return found or ["United States"]


def parse_brief(
    promoting_what: str,
    target_type: TargetType,
    settings: dict[str, str],
) -> IntakeResult:
    try:
        parsed = llm.generate_structured(_ParsedFields, SYSTEM_PROMPT, promoting_what, settings)
    except llm.LLMError as exc:
        status = (
            IntakeStatus.INVALID_GEMINI_KEY
            if exc.kind == llm.LLMErrorKind.INVALID_KEY
            else IntakeStatus.GEMINI_ERROR
        )
        return IntakeResult(_heuristic_brief(promoting_what, target_type), status, exc.message)

    if parsed is None:
        return IntakeResult(
            _heuristic_brief(promoting_what, target_type), IntakeStatus.NO_GEMINI_KEY, None
        )

    brief = Brief(
        product=parsed.product,
        audience=parsed.audience,
        tone=parsed.tone,
        target_type=target_type,
        niche_or_industry=parsed.niche_or_industry,
        target_countries=parsed.target_countries or ["United States"],
    )
    return IntakeResult(brief, IntakeStatus.LLM_OK, None)


def _heuristic_brief(promoting_what: str, target_type: TargetType) -> Brief:
    """A no-model fallback that still returns a valid Brief.

    Used whenever the model path didn't produce one — no key anywhere, a
    rejected credential, or any other Gemini failure — so intake never
    blocks the rest of the flow.
    """
    text = promoting_what.strip()
    niche = text[:80] if text else "General"
    audience = (
        "Distributors and logistics partners"
        if target_type == "business"
        else "Relevant content creators"
    )
    return Brief(
        product=text or "Unspecified product",
        audience=audience,
        tone="Professional",
        target_type=target_type,
        niche_or_industry=niche,
        target_countries=_extract_countries(text),
    )
