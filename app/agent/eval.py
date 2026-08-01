"""Score one draft against a fully-specified rubric, LLM judge or heuristic.

Mirrors intake.py/scoring.py/drafting.py's status-carrying shape (SPEC.md
§4.8). An LLM judge scores the rubric when a Gemini key is present and not
already known-rejected this request; a fully-specified deterministic
heuristic runs otherwise, producing the identical EvalResult shape so a
rendered score reads the same regardless of which path produced it.

Shared helpers reused, not reimplemented: this module imports
drafting._recipient_identity, drafting._norm_for_substring,
drafting._parse_fit_reasons, and drafting.BANNED_FILLER_PHRASES rather than
duplicating any of this logic — the same discipline scoring.py/drafting.py
already use for app.sources.base.canonical_name/coerce_int.
"""

import re
from dataclasses import dataclass
from enum import Enum

from app import llm
from app.agent import drafting
from app.models import Brief, EvalDimension, EvalResult, EvalRubric

SYSTEM_PROMPT_EVAL = """\
You judge one outreach message against a fixed rubric, scoring four
dimensions from 0 to 25 points each. Return exactly these four dimensions
and a total score equal to their sum.

1. personalization (0-25): does the message name and address the specific
   recipient, not a generic "there" or "team"? Full points only if a real
   recipient name or handle is given to you and the message actually uses it.
2. specificity (0-25): does the message cite one of the specific, verified
   facts given to you about this recipient, not a vague or generic claim?
   Full points only if a given fact's exact value appears in the message.
3. non_genericness (0-25): does the message avoid generic sales filler and
   read like it was written for this one recipient, with varied sentence
   structure rather than a templated cadence?
4. clear_ask (0-25): does the message make exactly one clear, specific ask,
   rather than no ask at all or several competing ones?

For every dimension, give a one-sentence justification grounded in the
message text you were given. Respond with a JSON object only.
"""


class EvalStatus(str, Enum):
    LLM_OK = "llm_ok"
    NO_GEMINI_KEY = "no_gemini_key"
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"


@dataclass
class EvalOutcome:
    result: EvalResult
    status: EvalStatus
    usage: list[llm.TokenUsage]
    model_used: str  # GEMINI_MODEL, the escalation model, or "heuristic"
    reason: str | None  # sanitized, safe for UI/audit


def evaluate_draft(
    brief: Brief,
    target: dict,
    draft_body: str,
    settings: dict[str, str],
    *,
    known_invalid_key_reason: str | None = None,
) -> EvalOutcome:
    """Score one drafted body against the rubric. Never raises.

    `known_invalid_key_reason` mirrors scoring.score_batch/drafting's
    parameter of the same name — if a caller already knows this Gemini key
    is rejected, skip the live call entirely rather than asking an
    already-rejected credential a second question.
    """
    if known_invalid_key_reason is not None:
        return EvalOutcome(
            result=_heuristic_eval(target, draft_body),
            status=EvalStatus.INVALID_GEMINI_KEY,
            usage=[],
            model_used="heuristic",
            reason=known_invalid_key_reason,
        )

    try:
        measured = llm.generate_structured_with_usage(
            EvalResult, SYSTEM_PROMPT_EVAL, _build_eval_prompt(brief, target, draft_body), settings
        )
    except llm.LLMError as exc:
        status = (
            EvalStatus.INVALID_GEMINI_KEY
            if exc.kind == llm.LLMErrorKind.INVALID_KEY
            else EvalStatus.GEMINI_ERROR
        )
        return EvalOutcome(
            result=_heuristic_eval(target, draft_body),
            status=status,
            usage=exc.usage,
            model_used="heuristic",
            reason=exc.message,
        )

    if measured.value is None:
        return EvalOutcome(
            result=_heuristic_eval(target, draft_body),
            status=EvalStatus.NO_GEMINI_KEY,
            usage=measured.usage,
            model_used="heuristic",
            reason=None,
        )

    return EvalOutcome(
        result=measured.value,
        status=EvalStatus.LLM_OK,
        usage=measured.usage,
        model_used=llm.GEMINI_MODEL,
        reason=None,
    )


def _build_eval_prompt(brief: Brief, target: dict, draft_body: str) -> str:
    identity = drafting._recipient_identity(target)
    reasons = drafting._parse_fit_reasons(target)
    facts = [
        {"key": r.get("evidence_key"), "value": r.get("evidence_value")}
        for r in reasons
    ]
    return (
        f"Recipient name/handle given to you (or none): {identity or 'none available'}\n\n"
        f"Verified facts about this recipient:\n{facts}\n\n"
        f"What we offer: {brief.product}\n\n"
        f"The message to judge:\n{draft_body}\n"
    )


# --- Deterministic heuristic rubric (demo-mode / no-key / fallback path) ----


def _sentences(body: str) -> list[str]:
    stripped = body.strip()
    if not stripped:
        return []
    parts = re.split(r"(?<=[.!?])\s+", stripped)
    return [p for p in parts if p.strip()]


def _heuristic_eval(target: dict, draft_body: str) -> EvalResult:
    if not draft_body or not draft_body.strip():
        zero = EvalDimension(points=0, justification="No draft body was available to score.")
        return EvalResult(
            rubric=EvalRubric(
                personalization=zero, specificity=zero, non_genericness=zero, clear_ask=zero
            ),
            score=0,
        )

    personalization = _score_personalization(target, draft_body)
    specificity = _score_specificity(target, draft_body)
    non_genericness = _score_non_genericness(draft_body)
    clear_ask = _score_clear_ask(draft_body)
    total = (
        personalization.points + specificity.points + non_genericness.points + clear_ask.points
    )
    return EvalResult(
        rubric=EvalRubric(
            personalization=personalization,
            specificity=specificity,
            non_genericness=non_genericness,
            clear_ask=clear_ask,
        ),
        score=total,
    )


def _score_personalization(target: dict, draft_body: str) -> EvalDimension:
    identity = drafting._recipient_identity(target)
    if identity is None:
        return EvalDimension(
            points=0,
            justification="No identifiable recipient name or handle was available to personalize with.",
        )
    body_norm = drafting._norm_for_substring(draft_body)
    if drafting._norm_for_substring(identity) in body_norm:
        return EvalDimension(points=25, justification=f"The message addresses {identity} directly.")
    return EvalDimension(
        points=0, justification=f"{identity} was available but is never named in the message."
    )


def _score_specificity(target: dict, draft_body: str) -> EvalDimension:
    reasons = drafting._parse_fit_reasons(target)
    if not reasons:
        return EvalDimension(
            points=0, justification="No stored evidence was available to check for a specific detail."
        )
    body_norm = drafting._norm_for_substring(draft_body)
    for reason in reasons:
        value = reason.get("evidence_value")
        if value and drafting._norm_for_substring(value) in body_norm:
            return EvalDimension(
                points=25, justification=f"The message cites a specific, verified detail ({value!r})."
            )
    return EvalDimension(
        points=0, justification="The message contains no specific, verifiable detail about the target."
    )


def _score_non_genericness(draft_body: str) -> EvalDimension:
    body_lower = draft_body.lower()
    has_banned = any(phrase in body_lower for phrase in drafting.BANNED_FILLER_PHRASES)
    banned_points = 0 if has_banned else 15

    sentences = _sentences(draft_body)
    lengths = [len(s.split()) for s in sentences if s.split()]
    variety_points = 10 if len(lengths) >= 2 and len(set(lengths)) > 1 else 0

    points = banned_points + variety_points
    if has_banned:
        phrase_note = "the message uses generic sales filler"
    else:
        phrase_note = "the message avoids generic sales filler"
    if variety_points:
        variety_note = "sentence lengths vary"
    else:
        variety_note = "sentence lengths don't vary"
    return EvalDimension(points=points, justification=f"{phrase_note.capitalize()}, and {variety_note}.")


def _score_clear_ask(draft_body: str) -> EvalDimension:
    sentences = _sentences(draft_body)
    question_count = sum(1 for s in sentences if s.rstrip().endswith("?"))
    if question_count == 1:
        return EvalDimension(points=25, justification="The message makes exactly one clear ask.")
    if question_count == 0:
        return EvalDimension(points=0, justification="The message makes no clear ask.")
    return EvalDimension(
        points=10, justification=f"The message makes {question_count} competing asks instead of one."
    )
