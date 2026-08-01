"""Generate one personalized outreach draft per target.

Mirrors intake.py/scoring.py's status-carrying shape. The LLM path returns a
structured OutreachDraft (body + the one evidence pair it cites), validated
by generate_structured's existing schema/retry machinery (non-negotiable #5).
That machinery cannot check semantic truth, so a second, runtime grounding
gate (_is_draft_grounded) verifies the cited pair is real for this target
(matches a Slice 3 grounded fit reason), the body actually uses it, and the
recipient is named when a real identity exists. A schema-valid but ungrounded
draft falls back to the deterministic heuristic below, which is grounded by
construction — it only ever cites a value it just read from the target's own
stored, already-verified evidence.

Zero keys still produces a usable, evidence-referencing draft (demo-mode
non-negotiable): _heuristic_draft never calls a model.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum

from app import llm
from app.models import Brief, OutreachDraft
from app.sources.base import DEFAULT_NAME

# Reused, not reimplemented: app/agent/eval.py's heuristic non_genericness
# dimension imports this constant rather than duplicating the phrase list, so
# SYSTEM_PROMPT's prose and the heuristic's check can never silently drift
# apart without a diff showing both. Lower-case; checked as a
# case-insensitive substring match against the normalized body.
BANNED_FILLER_PHRASES = (
    "i love what you're doing",
    "huge fan",
    "reaching out",
    "excited to connect",
    "explore synergies",
    "at its core",
    "in today's landscape",
)

SYSTEM_PROMPT = """\
You write one short outreach message from a business to a prospective partner
it wants to work with. A person will read every message before anything is
sent, and will reject anything that reads like a form letter.

You are given a few verified facts about this company, each as a key and an
exact value. Choose exactly one of those facts and build the message around it.
Reference that value in the message using the exact words given. Never invent a
fact, and never use a fact that was not given to you.

Address the company by name at least once, using the name given.

Make exactly one clear, small ask: a short reply, a quick call, a sample. Not a
meeting invite with five options. Not "let me know if you're interested."

Voice:
- Plain declarative sentences. Vary their length. A short one can land hard.
- Concrete nouns, strong verbs. Name the thing.
- No em dashes. Use periods and commas.
- No "not just X, it's Y" reversals.
- No opener flattery ("I love what you're doing", "huge fan"), no corporate
  filler ("reaching out", "excited to connect", "explore synergies", "at its
  core", "in today's landscape"), no emojis, straight quotes only.
- 60 to 110 words. A greeting, one or two sentences of specific relevance, one
  ask, a sign-off line the sender will fill in.

Return the message body, and the single evidence key and value you built it on.
"""

# Neutral lead sentences keyed by the chosen fit reason's evidence_key. Every
# value comes verbatim from that reason's evidence_value, and no template
# asserts the target is an ideal partner, a targeted market, or the right
# size — only scoring._heuristic knows whether a fact was actually favorable,
# and this heuristic never repeats that judgment as a claim.
_NEUTRAL_LEADS = {
    "industry": "I noticed {name} works in {value}.",
    "employees": "I saw that {name} has about {value} people.",
    "country": "I saw that {name} is based in {value}.",
    "name": "I came across {value}.",
}
_DEFAULT_LEAD = "I noticed this about {name}: {value}."


class DraftStatus(str, Enum):
    LLM_OK = "llm_ok"  # drafted by the model AND passed the grounding gate
    NO_GEMINI_KEY = "no_gemini_key"  # no key anywhere -> heuristic template
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"
    HEURISTIC_FALLBACK = "heuristic_fallback"  # model replied schema-valid but ungrounded


@dataclass
class DraftResult:
    body: str
    model_used: str  # the model that produced body on LLM_OK, "heuristic" otherwise
    status: DraftStatus
    reason: str | None  # sanitized, safe for audit; see module docstring
    usage: list[llm.TokenUsage] = field(default_factory=list)


def draft_outreach(
    brief: Brief,
    target: dict,
    settings: dict[str, str],
    *,
    known_invalid_key_reason: str | None = None,
    model: str = llm.GEMINI_MODEL,
) -> DraftResult:
    """Draft one outreach message for `target`.

    `target` is the persisted target row (dict-like), carrying at least
    `name`, `handle_or_domain`, and `fit_reasons_json` (Slice 3's grounded
    citations, as a JSON string). Never raises: every failure mode resolves
    to a DraftResult with a heuristic body.

    `known_invalid_key_reason` mirrors scoring.score_batch's parameter — if a
    caller already knows this Gemini key is rejected, skip the live call.

    `model` (Slice 6) lets app.agent.routing call this same function for the
    escalation tier through the identical drafting/grounding logic — only the
    model id sent to Gemini changes; heuristic behavior is unaffected.
    """
    if known_invalid_key_reason is not None:
        return DraftResult(
            body=_heuristic_draft(brief, target).body,
            model_used="heuristic",
            status=DraftStatus.INVALID_GEMINI_KEY,
            reason=known_invalid_key_reason,
            usage=[],
        )

    try:
        measured = llm.generate_structured_with_usage(
            OutreachDraft, SYSTEM_PROMPT, _build_prompt(brief, target), settings, model=model
        )
    except llm.LLMError as exc:
        status = (
            DraftStatus.INVALID_GEMINI_KEY
            if exc.kind == llm.LLMErrorKind.INVALID_KEY
            else DraftStatus.GEMINI_ERROR
        )
        return DraftResult(
            _heuristic_draft(brief, target).body, "heuristic", status, exc.message, usage=exc.usage
        )

    draft, usage = measured.value, measured.usage

    if draft is None:
        return DraftResult(
            _heuristic_draft(brief, target).body, "heuristic", DraftStatus.NO_GEMINI_KEY, None, usage=usage
        )

    if _is_draft_grounded(draft, target):
        return DraftResult(draft.body, model, DraftStatus.LLM_OK, None, usage=usage)

    return DraftResult(
        _heuristic_draft(brief, target).body,
        "heuristic",
        DraftStatus.HEURISTIC_FALLBACK,
        "model draft did not pass the grounding check",
        usage=usage,
    )


def _build_prompt(brief: Brief, target: dict) -> str:
    facts = [
        {"key": r.get("evidence_key"), "value": r.get("evidence_value")}
        for r in _parse_fit_reasons(target)
    ]
    return (
        f"Company name: {target.get('name') or DEFAULT_NAME}\n\n"
        f"Verified facts about this company (choose exactly one):\n{json.dumps(facts, indent=2)}\n\n"
        f"What we offer: {brief.product}\n"
        f"Who we usually work with: {brief.audience}\n"
    )


def _parse_fit_reasons(target: dict) -> list[dict]:
    raw = target.get("fit_reasons_json")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _recipient_identity(target: dict) -> str | None:
    """The name to use in a greeting/reference, or None if there isn't one
    meaningful enough to require (SPEC.md §4.4 point 4)."""
    name = target.get("name")
    if name and name != DEFAULT_NAME:
        return name
    handle = target.get("handle_or_domain")
    if handle:
        return handle
    return None


def _norm(value: object) -> str:
    """Exact-match normalization for the evidence pair, mirroring Slice 3's
    scoring._norm — the cited pair is checked for identity, not substring."""
    return str(value).strip().lower()


def _norm_for_substring(value: object) -> str:
    """Prose comparison: lowercase, collapse internal whitespace, strip.
    Used only for the body/identity substring checks — prose is
    paraphrasable, so this is deliberately looser than the exact-match pair
    check above (a short numeric value could match incidentally; accepted
    as a known limitation for a demo-scale grounding gate)."""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _is_draft_grounded(draft: OutreachDraft, target: dict) -> bool:
    """True iff the model's cited pair is real for this target, the body
    uses it, and the recipient is named when one meaningfully exists."""
    fit_reasons = _parse_fit_reasons(target)
    pair_is_real = any(
        _norm(r.get("evidence_key")) == _norm(draft.evidence_key)
        and _norm(r.get("evidence_value")) == _norm(draft.evidence_value)
        for r in fit_reasons
    )
    if not pair_is_real:
        return False

    value_norm = _norm_for_substring(draft.evidence_value)
    if not value_norm:
        return False

    body_norm = _norm_for_substring(draft.body)
    if value_norm not in body_norm:
        return False

    identity = _recipient_identity(target)
    if identity is not None and _norm_for_substring(identity) not in body_norm:
        return False

    return True


def _heuristic_draft(brief: Brief, target: dict) -> OutreachDraft:
    """Zero-key / fallback path. Reads the target's first stored grounded
    fit reason and states its value neutrally — never as a claim that the
    fact proves a good fit, since a stored reason may describe a poor one.

    Post-Slice-3 every persisted target has at least one stored reason
    (scoring.assert_grounded guarantees it before persistence), so there is
    always a real fact to cite. The no-reasons branch below is a defensive
    fallback for that otherwise-unreachable case.
    """
    fit_reasons = _parse_fit_reasons(target)
    identity = _recipient_identity(target)
    display_name = target.get("name") or DEFAULT_NAME
    greeting_name = identity or "there"

    if fit_reasons:
        chosen = fit_reasons[0]
        key = chosen.get("evidence_key") or "name"
        value = chosen.get("evidence_value") or display_name
    else:
        key, value = "name", display_name

    lead = _NEUTRAL_LEADS.get(key, _DEFAULT_LEAD).format(name=display_name, value=value)

    body = (
        f"Hi {greeting_name},\n\n"
        f"{lead}\n\n"
        f"We make {brief.product}. Would you be open to a short reply to see "
        "if it's worth a quick call?\n\n"
        "Best,\n[Your name]"
    )

    return OutreachDraft(body=body, evidence_key=key, evidence_value=str(value))
