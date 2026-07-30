"""Explicit status -> audit action -> banner maps.

No status is ever turned into an audit action via string interpolation of
the enum value — that would silently rename NO_KEY's action from the
intended "discovery.no_apollo_key" to "discovery.no_key". Both main.py (real
behavior) and tests/test_slice2_hardening.py import these same maps, so what
is tested is guaranteed to match production.
"""

from app.agent.intake import IntakeStatus
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

BANNER_BY_ACTION: dict[str, tuple[str, str]] = {
    action: (severity, template)
    for action, severity, template in [*DISCOVERY_MAP.values(), *INTAKE_MAP.values()]
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
