"""Explicit status -> audit action -> banner maps.

No status is ever turned into an audit action via string interpolation of
the enum value — that would silently rename NO_KEY's action from the
intended "discovery.no_apollo_key" to "discovery.no_key". Both main.py (real
behavior) and tests/test_slice2_hardening.py import these same maps, so what
is tested is guaranteed to match production.
"""

from app.agent.intake import IntakeStatus
from app.agent.scoring import ScoreStatus
from app.sources.base import SourceStatus

DISCOVERY_MAP: dict[SourceStatus, tuple[str, str | None, str | None]] = {
    # status: (audit_action, banner_severity, banner_template)
    SourceStatus.OK: ("discovery.apollo_ok", None, None),  # no banner on success
    SourceStatus.NO_KEY: (
        "discovery.no_apollo_key",
        "info",
        "Using seed data (no Apollo key). Paste an Apollo key in Settings to search live companies.",
    ),
    SourceStatus.INVALID_KEY: (
        "discovery.invalid_apollo_key",
        "warning",
        "Apollo rejected the request ({reason}). Falling back to seed data — check your Apollo key in Settings.",
    ),
    SourceStatus.INSUFFICIENT_PLAN: (
        "discovery.insufficient_plan",
        "warning",
        "Apollo rejected the request ({reason}). Falling back to seed data — your Apollo plan doesn't include company search.",
    ),
    SourceStatus.RATE_LIMITED: (
        "discovery.rate_limited",
        "warning",
        "Apollo is rate-limiting requests right now ({reason}). Falling back to seed data — try again in a little while; your key is fine.",
    ),
    SourceStatus.PROVIDER_ERROR: (
        "discovery.provider_error",
        "warning",
        "Apollo couldn't complete the search ({reason}). Falling back to seed data — this is a problem on Apollo's side, not your key.",
    ),
    SourceStatus.NETWORK_ERROR: (
        "discovery.network_error",
        "warning",
        "Couldn't reach Apollo ({reason}). Falling back to seed data — check your connection and try again.",
    ),
    SourceStatus.SEED_ERROR: (
        "discovery.seed_error",
        "warning",
        "Discovery couldn't load any targets ({reason}). No results to show — this is a local data problem, not your Apollo key.",
    ),
}

INTAKE_MAP: dict[IntakeStatus, tuple[str, str | None, str | None]] = {
    IntakeStatus.LLM_OK: ("intake.llm_ok", None, None),
    IntakeStatus.NO_GEMINI_KEY: (
        "intake.no_gemini_key",
        "info",
        "Parsed with the built-in heuristic (no Gemini key). Paste a Gemini key in Settings for LLM-parsed briefs.",
    ),
    IntakeStatus.INVALID_GEMINI_KEY: (
        "intake.invalid_gemini_key",
        "warning",
        "Gemini rejected the request ({reason}). Parsed with the built-in heuristic instead — check your Gemini key in Settings.",
    ),
    IntakeStatus.GEMINI_ERROR: (
        "intake.gemini_error",
        "warning",
        "Gemini couldn't complete the request ({reason}). Parsed with the built-in heuristic instead.",
    ),
}

SCORING_MAP: dict[ScoreStatus, tuple[str, str | None, str | None]] = {
    ScoreStatus.LLM_OK: ("scoring.llm_ok", None, None),  # silent on success
    ScoreStatus.PARTIAL_HEURISTIC: (
        "scoring.partial_heuristic",
        "info",
        "Some targets were scored with the built-in heuristic ({reason}).",
    ),
    ScoreStatus.NO_GEMINI_KEY: (
        "scoring.no_gemini_key",
        "info",
        "Fit scored with the built-in heuristic (no Gemini key). Paste a Gemini key in Settings for LLM-scored fit.",
    ),
    ScoreStatus.INVALID_GEMINI_KEY: (
        "scoring.invalid_gemini_key",
        "warning",
        "Gemini rejected the scoring request ({reason}). Scored with the built-in heuristic instead — check your Gemini key in Settings.",
    ),
    ScoreStatus.GEMINI_ERROR: (
        "scoring.gemini_error",
        "warning",
        "Gemini couldn't complete scoring ({reason}). Scored with the built-in heuristic instead.",
    ),
}

BANNER_BY_ACTION: dict[str, tuple[str, str]] = {
    action: (severity, template)
    for action, severity, template in [*DISCOVERY_MAP.values(), *INTAKE_MAP.values(), *SCORING_MAP.values()]
    if severity is not None
}


def banner_for(action: str, detail: str | None) -> tuple[str, str] | None:
    """Return (severity, rendered_text) for a persisted audit row, or None
    (OK/LLM_OK actions aren't in BANNER_BY_ACTION and render nothing)."""
    entry = BANNER_BY_ACTION.get(action)
    if entry is None:
        return None
    severity, template = entry
    return severity, template.format(reason=detail or "")


# Slice 4 draft/pipeline actions are human/agent actions recorded straight to
# the audit table, not campaign banners (the banner filter stays intake /
# discovery / scoring) — but the campaign Activity list (§7.3) needs a human
# label for every action it renders, including these plus the existing
# intake/discovery/scoring ones. Explicit map, not enum-string interpolation,
# same discipline as DISCOVERY_MAP/INTAKE_MAP/SCORING_MAP above.
DRAFT_CREATED = "draft.created"
DRAFT_EDITED = "draft.edited"
DRAFT_APPROVED = "draft.approved"
DRAFT_REJECTED = "draft.rejected"
TARGET_STAGE_CHANGED = "target.stage_changed"

ACTION_LABELS: dict[str, str] = {
    "intake.llm_ok": "Brief parsed",
    "intake.no_gemini_key": "Brief parsed (heuristic)",
    "intake.invalid_gemini_key": "Brief parsed (heuristic, Gemini key rejected)",
    "intake.gemini_error": "Brief parsed (heuristic, Gemini error)",
    "discovery.apollo_ok": "Discovery ran (Apollo)",
    "discovery.no_apollo_key": "Discovery ran (seed data)",
    "discovery.invalid_apollo_key": "Discovery ran (seed data, Apollo key rejected)",
    "discovery.insufficient_plan": "Discovery ran (seed data, Apollo plan limit)",
    "discovery.rate_limited": "Discovery ran (seed data, Apollo rate-limited)",
    "discovery.provider_error": "Discovery ran (seed data, Apollo error)",
    "discovery.network_error": "Discovery ran (seed data, network error)",
    "discovery.seed_error": "Discovery failed",
    "scoring.llm_ok": "Targets scored",
    "scoring.partial_heuristic": "Targets scored (partially heuristic)",
    "scoring.no_gemini_key": "Targets scored (heuristic)",
    "scoring.invalid_gemini_key": "Targets scored (heuristic, Gemini key rejected)",
    "scoring.gemini_error": "Targets scored (heuristic, Gemini error)",
    "scoring.skipped_no_targets": "Scoring skipped (no targets)",
    DRAFT_CREATED: "Draft created",
    DRAFT_EDITED: "Draft edited",
    DRAFT_APPROVED: "Draft approved",
    DRAFT_REJECTED: "Draft rejected",
    TARGET_STAGE_CHANGED: "Stage changed",
}


def label_for(action: str) -> str:
    """A human phrase for an audit action, or a sensible default so an
    unmapped action never crashes the Activity list."""
    return ACTION_LABELS.get(action, action.replace(".", " ").replace("_", " ").capitalize())
