"""Model-tier routing, terminal invalid-key handling, and per-outreach cost.

Takes an explicit `paid_tier_enabled` boolean (resolved once by main.py from
the workspace already in scope there) and performs no database access of any
kind — the tenant-isolation guarantee for this data stays anchored at the
one call site that actually has a workspace_id, not spread into a module
with no database dependency otherwise (SLICE_6_PLAN.md §0.2 correction 4).

Escalation is fully implemented and mocked-tested but cannot fire until the
owner sets a verified ESCALATION_MODEL (decision 5/6 of the plan) *and* a
workspace opts in — the code gate is `ESCALATION_MODEL is None`, checked in
step 4 below.

Invalid credentials are terminal after every model-backed stage (default
draft, default eval, escalated draft, escalated eval): the first
INVALID_GEMINI_KEY outcome stops every later Gemini call in this operation,
while every usage entry already collected is preserved in cost_breakdown —
none of it is discarded just because the operation ends early.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app import llm
from app.agent import drafting
from app.agent import eval as eval_mod
from app.agent.drafting import DraftStatus
from app.agent.eval import EvalOutcome, EvalStatus
from app.models import Brief, EvalResult

HIGH_FIT_THRESHOLD = 85       # inclusive
CONFIDENCE_THRESHOLD = 80     # inclusive
ESCALATION_MODEL: str | None = None  # unset until owner-verified (decision 5/6)

# Time-sensitive, provider-controlled pricing — re-verify against the
# official Gemini API pricing page before relying on a figure (the same
# discipline Slice 5 used for Apify/YouTube pricing: SLICE_5_PLAN.md §4.3).
# Verified 2026-08-01 against https://ai.google.dev/gemini-api/docs/latest-model.
# Only two rates per model: Google prices output inclusive of thinking
# tokens for these tool-free structured-output requests, so there is no
# separate "thinking" rate to configure.
PRICING_USD_PER_MILLION_TOKENS: dict[str, dict[str, Decimal]] = {
    "gemini-3.6-flash": {
        "input": Decimal("1.50"),
        "output": Decimal("7.50"),
    },
    # ESCALATION_MODEL's entry is added once the owner approves that model
    # id and its official pricing is verified (decision 5/6).
}


@dataclass
class RoutingOutcome:
    body: str
    model_used: str
    eval_result: EvalResult
    eval_status: EvalStatus
    cost_breakdown: list[llm.TokenUsage]
    cost_tokens: int | None            # None means unknown, 0 means no request issued
    estimated_cost_microusd: int | None
    routing_action: str  # "default" | "early_exit" | "escalated"
                          # | "escalation_unavailable" | "invalid_key_terminal"
    # Elaborations beyond the plan's minimal field list, needed by
    # db.create_draft_with_routing (SLICE_6_PLAN.md §5.6) to write the same
    # kind of informative draft.created/routing audit detail Slices 2-5
    # already write — never required by routing logic itself.
    routing_detail: str | None = None  # terminal stage name, only set for invalid_key_terminal
    draft_status: DraftStatus = DraftStatus.NO_GEMINI_KEY
    draft_reason: str | None = None
    eval_reason: str | None = None


def route_and_draft(
    brief: Brief,
    target: dict,
    settings: dict[str, str],
    *,
    paid_tier_enabled: bool,
) -> RoutingOutcome:
    """Draft, evaluate, and (only when eligible) escalate one outreach
    message, accumulating every issued Gemini attempt's usage in order.

    Never raises: every drafting/eval failure mode already resolves to a
    heuristic result one level down (drafting.draft_outreach,
    eval.evaluate_draft never raise either).
    """
    cost_breakdown: list[llm.TokenUsage] = []

    # 1. Default draft.
    default_draft = drafting.draft_outreach(brief, target, settings)
    cost_breakdown.extend(default_draft.usage)

    # 2. Terminal check after default drafting.
    if default_draft.status == DraftStatus.INVALID_GEMINI_KEY:
        eval_outcome = eval_mod.evaluate_draft(
            brief, target, default_draft.body, settings,
            known_invalid_key_reason=default_draft.reason,
        )
        cost_breakdown.extend(eval_outcome.usage)
        return _finish(
            default_draft, eval_outcome, cost_breakdown, "invalid_key_terminal", "default_draft"
        )

    # 3. Evaluate the default draft.
    default_eval = eval_mod.evaluate_draft(brief, target, default_draft.body, settings)
    cost_breakdown.extend(default_eval.usage)

    if default_eval.status == EvalStatus.INVALID_GEMINI_KEY:
        return _finish(
            default_draft, default_eval, cost_breakdown, "invalid_key_terminal", "default_eval"
        )

    # 4. Escalation eligibility (only after both terminal checks pass).
    fit_score = target.get("fit_score")
    eligible = (
        bool(settings.get("gemini"))
        and paid_tier_enabled
        and fit_score is not None
        and fit_score >= HIGH_FIT_THRESHOLD
    )
    if not eligible:
        return _finish(default_draft, default_eval, cost_breakdown, "default", None)
    if ESCALATION_MODEL is None:
        return _finish(default_draft, default_eval, cost_breakdown, "escalation_unavailable", None)

    # 5. Confidence early-exit / escalation with terminal checks.
    if default_eval.result.score >= CONFIDENCE_THRESHOLD:
        return _finish(default_draft, default_eval, cost_breakdown, "early_exit", None)

    escalated_draft = drafting.draft_outreach(brief, target, settings, model=ESCALATION_MODEL)
    cost_breakdown.extend(escalated_draft.usage)

    if escalated_draft.status == DraftStatus.INVALID_GEMINI_KEY:
        # Keep the already-valid default body/eval; no escalated-eval call.
        return _finish(
            default_draft, default_eval, cost_breakdown, "invalid_key_terminal", "escalated_draft"
        )

    escalated_eval = eval_mod.evaluate_draft(brief, target, escalated_draft.body, settings)
    cost_breakdown.extend(escalated_eval.usage)

    if escalated_eval.status == EvalStatus.INVALID_GEMINI_KEY:
        return _finish(
            escalated_draft, escalated_eval, cost_breakdown, "invalid_key_terminal", "escalated_eval"
        )

    return _finish(escalated_draft, escalated_eval, cost_breakdown, "escalated", None)


def _finish(
    draft_result,  # app.agent.drafting.DraftResult — the DraftResult whose body/model_used is stored
    eval_outcome: EvalOutcome,
    cost_breakdown: list[llm.TokenUsage],
    routing_action: str,
    routing_detail: str | None,
) -> RoutingOutcome:
    cost_tokens, estimated_cost_microusd = _price(cost_breakdown)
    return RoutingOutcome(
        body=draft_result.body,
        model_used=draft_result.model_used,
        eval_result=eval_outcome.result,
        eval_status=eval_outcome.status,
        cost_breakdown=cost_breakdown,
        cost_tokens=cost_tokens,
        estimated_cost_microusd=estimated_cost_microusd,
        routing_action=routing_action,
        routing_detail=routing_detail,
        draft_status=draft_result.status,
        draft_reason=draft_result.reason,
        eval_reason=eval_outcome.reason,
    )


def _price(cost_breakdown: list[llm.TokenUsage]) -> tuple[int | None, int | None]:
    """(cost_tokens, estimated_cost_microusd) for one outreach's full usage
    list, per SLICE_6_PLAN.md §4.4/§4.5. The two aggregates are computed and
    can be unknown independently of each other — a known total_tokens count
    does not guarantee a known dollar estimate, since pricing additionally
    requires a known prompt_tokens and a recognized model.

    `cost_breakdown == []` (no Gemini request issued anywhere) is the only
    case returning (0, 0) — a known zero, never conflated with unknown.
    """
    if not cost_breakdown:
        return 0, 0

    cost_tokens = None
    if all(u.total_tokens is not None for u in cost_breakdown):
        cost_tokens = sum(u.total_tokens for u in cost_breakdown)

    exact_microusd = Decimal("0")
    for usage in cost_breakdown:
        rates = PRICING_USD_PER_MILLION_TOKENS.get(usage.model)
        if (
            usage.prompt_tokens is None
            or usage.total_tokens is None
            or usage.prompt_tokens < 0
            or usage.total_tokens < usage.prompt_tokens
            or rates is None
        ):
            return cost_tokens, None
        exact_microusd += (
            Decimal(usage.prompt_tokens) * rates["input"]
            + Decimal(usage.total_tokens - usage.prompt_tokens) * rates["output"]
        )

    estimated_cost_microusd = int(exact_microusd.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return cost_tokens, estimated_cost_microusd
