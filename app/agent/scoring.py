"""Fit-scoring for discovered targets, with grounded citations.

Scores the whole batch of discovered targets in a single structured LLM call
(a FitBatch), rather than one call per target: this bounds latency
independent of target count, and turns a rejected credential into a single
403 rather than a retry loop. A citation is not trusted just because the
schema shape is valid — every reason's evidence_key/evidence_value is checked
against the target's own normalized evidence before it is ever stored; a
missing assessment, or one with any ungrounded reason, falls back to the
deterministic heuristic for that single target. Every reason the heuristic
does produce is grounded by construction — it only ever cites a value it just
read from that target's own evidence, never a fabricated placeholder.

If intake already learned this same Gemini key is rejected earlier in the
same request, the caller passes known_invalid_key_reason so scoring skips
its own live call rather than asking an already-rejected credential a second
question.

"No score without a citation" (SPEC.md) is upheld two ways: the heuristic
always grounds at least one reason (it relies on a source/evidence contract —
every Source's normalize_evidence() must guarantee a nonblank "name" field —
and raises UngroundedEvidenceError if that contract is ever violated, rather
than silently returning a citation-free score), and assert_grounded() is a
second, independent check callers run just before persistence.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum

from app import llm
from app.models import Brief, FitAssessment, FitBatch, FitReason

SYSTEM_PROMPT = (
    "You score how well each candidate company fits a business's outreach "
    "campaign, on a 0-100 scale. For every target, give at least one reason "
    "that cites a specific evidence field and its exact value from that "
    "target's own evidence. Never cite a field that is missing, blank, or "
    "not present for that target, and never invent a field or value. "
    "Respond with a JSON object only."
)

# Stopwords dropped during industry/niche tokenization. Domain words like
# "distribution" or "logistics" are deliberately NOT included.
_STOPWORDS = {"and", "&", "the", "of", "for", "a", "an", "to", "in", "or"}


class ScoreStatus(str, Enum):
    LLM_OK = "llm_ok"                          # batch scored by the LLM, all grounded
    PARTIAL_HEURISTIC = "partial_heuristic"    # LLM scored, but >=1 target fell back
    NO_GEMINI_KEY = "no_gemini_key"            # no key anywhere -> all heuristic
    INVALID_GEMINI_KEY = "invalid_gemini_key"  # credential rejected -> all heuristic
    GEMINI_ERROR = "gemini_error"              # other Gemini failure -> all heuristic


@dataclass
class TargetScore:
    fit_score: int
    reasons: list[FitReason]
    scored_by: str  # "llm" or "heuristic"


@dataclass
class ScoreOutcome:
    scores: list[TargetScore]  # aligned 1:1 with the input evidence_list
    status: ScoreStatus
    llm_scored: int
    heuristic_scored: int
    reason: str | None  # sanitized, safe for UI/audit; None unless a failure occurred


class UngroundedEvidenceError(RuntimeError):
    """Raised when a score has no citation, or a citation that doesn't
    ground against its target's own evidence — the "no score without a
    citation" guarantee (SPEC.md) about to be violated.

    Should be unreachable in normal operation: every current Source's
    normalize_evidence() guarantees a nonblank "name" field, so the
    heuristic can always ground at least one reason, and the LLM path is
    already checked reason-by-reason before being trusted (_apply_batch).
    A raise here means a Source (or a future one) violated that contract —
    controlled invalid source/evidence data, not something to paper over
    with a fabricated citation or a silently empty reasons list.
    """


def score_batch(
    brief: Brief,
    evidence_list: list[dict],
    settings: dict[str, str],
    *,
    known_invalid_key_reason: str | None = None,
) -> ScoreOutcome:
    """Score every target in evidence_list with one structured LLM call.

    Falls back to the deterministic heuristic per-target whenever the LLM is
    unavailable, fails, or returns an assessment that doesn't ground to that
    target's own evidence. Never raises for a well-formed evidence dict — one
    whose Source honored the nonblank-"name" contract (see
    UngroundedEvidenceError). Raises only if that contract itself was
    violated, which is a bug in the Source, not an operational condition
    callers need to handle.

    known_invalid_key_reason: set by the caller when this same Gemini key was
    already rejected earlier in the same request (during intake). Skips the
    live call entirely rather than asking Gemini a second question with a
    credential already known to fail it — a rejected key doesn't become valid
    between two calls in the same request.
    """
    if not evidence_list:
        return ScoreOutcome(scores=[], status=ScoreStatus.LLM_OK, llm_scored=0, heuristic_scored=0, reason=None)

    if known_invalid_key_reason is not None:
        scores = [_heuristic_score(brief, ev) for ev in evidence_list]
        return ScoreOutcome(
            scores=scores, status=ScoreStatus.INVALID_GEMINI_KEY, llm_scored=0,
            heuristic_scored=len(scores), reason=known_invalid_key_reason,
        )

    try:
        batch = llm.generate_structured(
            FitBatch, SYSTEM_PROMPT, _build_prompt(brief, evidence_list), settings
        )
    except llm.LLMError as exc:
        status = (
            ScoreStatus.INVALID_GEMINI_KEY
            if exc.kind == llm.LLMErrorKind.INVALID_KEY
            else ScoreStatus.GEMINI_ERROR
        )
        scores = [_heuristic_score(brief, ev) for ev in evidence_list]
        return ScoreOutcome(
            scores=scores, status=status, llm_scored=0, heuristic_scored=len(scores), reason=exc.message
        )

    if batch is None:
        scores = [_heuristic_score(brief, ev) for ev in evidence_list]
        return ScoreOutcome(
            scores=scores, status=ScoreStatus.NO_GEMINI_KEY, llm_scored=0,
            heuristic_scored=len(scores), reason=None,
        )

    return _apply_batch(brief, evidence_list, batch)


def _build_prompt(brief: Brief, evidence_list: list[dict]) -> str:
    targets_block = json.dumps(
        [{"target_index": i, "evidence": ev} for i, ev in enumerate(evidence_list)],
        indent=2,
    )
    return (
        "Brief:\n"
        f"- product: {brief.product}\n"
        f"- audience: {brief.audience}\n"
        f"- niche_or_industry: {brief.niche_or_industry}\n"
        f"- target_countries: {', '.join(brief.target_countries)}\n\n"
        "Score every target below (by its target_index) for fit with this brief.\n"
        f"{targets_block}"
    )


def _apply_batch(brief: Brief, evidence_list: list[dict], batch: FitBatch) -> ScoreOutcome:
    """Resolve a validated FitBatch against evidence_list, grounding every citation.

    A missing target_index, a duplicate (first-seen wins, the rest are
    ignored), an out-of-range index, or any reason that fails grounding all
    result in that single target falling back to the heuristic — never the
    whole batch.
    """
    by_index: dict[int, FitAssessment] = {}
    for assessment in batch.assessments:
        idx = assessment.target_index
        if idx < 0 or idx >= len(evidence_list) or idx in by_index:
            continue
        by_index[idx] = assessment

    scores: list[TargetScore] = []
    llm_scored = 0
    heuristic_scored = 0
    for i, evidence in enumerate(evidence_list):
        assessment = by_index.get(i)
        if assessment is not None and all(_is_grounded(r, evidence) for r in assessment.reasons):
            scores.append(TargetScore(assessment.fit_score, assessment.reasons, "llm"))
            llm_scored += 1
        else:
            scores.append(_heuristic_score(brief, evidence))
            heuristic_scored += 1

    if heuristic_scored == 0:
        return ScoreOutcome(scores, ScoreStatus.LLM_OK, llm_scored, heuristic_scored, None)
    reason = f"{heuristic_scored} of {len(evidence_list)} target(s) fell back to the built-in heuristic"
    return ScoreOutcome(scores, ScoreStatus.PARTIAL_HEURISTIC, llm_scored, heuristic_scored, reason)


def _norm(value: object) -> str:
    return str(value).strip().lower()


def _is_grounded(reason: FitReason, evidence: dict) -> bool:
    """True iff the citation names a real, non-blank evidence field and value.

    A key that exists but carries no value (None, or an empty/whitespace
    string) can never ground a citation — several normalized-evidence fields
    (industry, employees, country) are legitimately None for real rows, so
    "the key exists" alone is not enough.
    """
    if reason.evidence_key not in evidence:
        return False
    value = evidence[reason.evidence_key]
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return _norm(value) == _norm(reason.evidence_value)


def assert_grounded(evidence_list: list[dict], scores: list[TargetScore]) -> None:
    """Defense-in-depth check: run just before persistence, not instead of
    score_batch upholding "no score without a citation" on its own.

    evidence_list and scores must be aligned 1:1 (the same order score_batch
    was called and returned with). Raises UngroundedEvidenceError if any
    score has zero reasons, or any reason doesn't ground against that same
    target's evidence — covering both the LLM path and the heuristic path,
    and any future scoring path, with one independent check.
    """
    for evidence, score in zip(evidence_list, scores):
        if not score.reasons:
            raise UngroundedEvidenceError("a target score has zero reasons")
        for reason in score.reasons:
            if not _is_grounded(reason, evidence):
                raise UngroundedEvidenceError(
                    f"citation {reason.evidence_key!r} does not match its target's evidence"
                )


# --- Deterministic heuristic (demo-mode / no-key path) ----------------------


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    words = re.split(r"[^a-z0-9]+", text.lower())
    return {w for w in words if w and w not in _STOPWORDS}


# Longest-first so "distributors" doesn't get incorrectly caught by a
# shorter suffix before the one that actually produces its true root.
_SUFFIXES = ("ations", "ation", "ions", "ion", "ers", "ors", "er", "or", "ing", "ed", "es", "s", "e")


def _stem(word: str) -> str:
    """A minimal suffix strip — not a real stemmer, just enough that
    "distribution"/"distributor"/"distributors" (and similar noun/verb
    variants of the same root) count as the same term for industry-overlap
    scoring. Only strips when >=3 characters of root remain, so short words
    are left alone.
    """
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _stemmed_tokens(text: str | None) -> set[str]:
    return {_stem(w) for w in _tokens(text)}


def _significant_niche_tokens(niche_or_industry: str | None) -> set[str]:
    """Stemmed niche/industry tokens, with short tokens excluded before
    they're used as the industry-overlap denominator.

    A free-text niche_or_industry description (the zero-key heuristic
    intake path sets this to the user's raw sentence, up to 80 characters)
    often includes an incidental geography abbreviation ("US distributors
    for magnesium") that isn't itself an industry descriptor. A token
    shorter than 3 characters is almost never a substantive industry word
    on its own, so counting it in the denominator unfairly dilutes a
    genuine industry match. This is general — not tied to any specific
    brief, company, or word list; it excludes by length, not by content.

    (An earlier version of this function also tried to exclude tokens
    shared with brief.product, on the theory that the product name leaking
    into free-text niche input is dilution too. That doesn't work: the same
    zero-key heuristic intake path that produces this free-text niche also
    sets brief.product to the identical raw sentence, so "product" and
    "niche" tokens are always the same set there — the exclusion emptied
    itself out via its own safety fallback and never fired. Removed rather
    than kept as dead code.)

    Falls back to the raw tokens if the length filter would empty the set —
    losing the ability to match anything at all would be worse than the
    dilution this function exists to fix.
    """
    niche_tokens = _stemmed_tokens(niche_or_industry)
    significant = {t for t in niche_tokens if len(t) >= 3}
    return significant or niche_tokens


def _heuristic_score(brief: Brief, evidence: dict) -> TargetScore:
    score, reasons = _heuristic(brief, evidence)
    return TargetScore(score, reasons, "heuristic")


def _heuristic(brief: Brief, evidence: dict) -> tuple[int, list[FitReason]]:
    """A pure function of the evidence: stable, testable, always grounded.

    Three additive components (industry overlap 0-60, size band 0-25, country
    match 0-15). A component whose evidence field is missing contributes 0
    points and emits no reason (a reason can't cite a value that isn't
    there); a component whose field IS present always emits exactly one
    reason, whether or not it scored well, so a fabricated citation is never
    needed to explain a low score. Raises UngroundedEvidenceError in the one
    case where even the final name-only fallback (see below) has nothing to
    cite — see that exception's docstring.
    """
    total = 0
    reasons: list[FitReason] = []

    industry = evidence.get("industry")
    if industry:
        niche_tokens = _significant_niche_tokens(brief.niche_or_industry)
        overlap = len(niche_tokens & _stemmed_tokens(industry))
        points = round(60 * overlap / max(1, len(niche_tokens)))
        total += points
        reason_text = (
            f"Industry overlaps with the brief's niche ({overlap} matching term(s))"
            if overlap
            # This component only evaluates niche_or_industry — brief.product
            # is never read here, so the explanation must not claim otherwise.
            else "Industry doesn't match the brief's niche"
        )
        reasons.append(FitReason(reason=reason_text, evidence_key="industry", evidence_value=str(industry)))

    employees = evidence.get("employees")
    if isinstance(employees, bool):
        employees = None  # bool is an int subclass in Python; not a real count
    elif not isinstance(employees, int):
        employees = None  # any other unexpected type (e.g. a string) is unusable, not a crash
    if employees is not None:
        if 100 <= employees <= 600:
            points = 25
            reason_text = f"Company size ({employees} employees) is a strong fit for a distribution/logistics partner"
        elif 50 <= employees <= 99 or 601 <= employees <= 1000:
            points = 15
            reason_text = f"Company size ({employees} employees) is a moderate fit"
        else:
            points = 5
            reason_text = f"Company size ({employees} employees) is outside the ideal range"
        total += points
        reasons.append(FitReason(reason=reason_text, evidence_key="employees", evidence_value=str(employees)))

    country = evidence.get("country")
    if country:
        if country in brief.target_countries:
            points = 15
            reason_text = f"Located in a targeted country ({country})"
        else:
            points = 0
            reason_text = f"Not located in a targeted country ({country})"
        total += points
        reasons.append(FitReason(reason=reason_text, evidence_key="country", evidence_value=str(country)))

    if not reasons:
        # No usable industry/employees/country field at all: cite the one
        # field every Source's normalize_evidence() is contractually
        # required to leave nonblank (name) rather than a fabricated
        # placeholder — citing anything that isn't the literal evidence
        # value would itself be an ungrounded reason, the exact thing this
        # module exists to prevent. A blank name here means that contract
        # was violated; raise rather than silently persist a citation-free
        # score (SPEC.md's "no score without a citation" is a guarantee,
        # not a best-effort).
        name = evidence.get("name")
        if not isinstance(name, str) or not name.strip():
            raise UngroundedEvidenceError(
                "evidence has no industry/employees/country and no usable name to cite"
            )
        reasons.append(
            FitReason(
                reason="No structured evidence fields (industry, size, or country) were available to score",
                evidence_key="name",
                evidence_value=name.strip(),
            )
        )

    return min(100, max(0, total)), reasons
