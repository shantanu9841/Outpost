"""Retained tests for Slice 6 (evaluation and cost-aware routing).

Mirrors the Slice 2-5 test discipline: every Gemini call is mocked at
app.llm.generate_structured_with_usage or httpx.post — no real provider
call, no real key, no outpost.db writes (a temporary SQLite file is used
wherever a DB is touched). Section headers below map to
docs/plans/SLICE_6_PLAN.md §6's numbered acceptance criteria.

Run: python -m unittest tests.test_slice6_eval_routing -v
"""

import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest import mock

import httpx
from pydantic import BaseModel

from app import audit_banners, db, llm
from app.agent import drafting, routing
from app.agent import eval as eval_mod
from app.agent.drafting import DraftStatus
from app.agent.eval import EvalStatus
from app.models import Brief, EvalDimension, EvalResult, EvalRubric, OutreachDraft


@contextmanager
def _escalation_enabled(model="escalation-fake", input_rate="2.00", output_rate="4.00"):
    """Patch both ESCALATION_MODEL and a matching pricing entry — after the
    review correction requiring verified pricing before escalation can run
    (finding 3), a model id alone is no longer enough to make
    `routing._escalation_ready()` true."""
    with mock.patch.object(routing, "ESCALATION_MODEL", model), mock.patch.dict(
        routing.PRICING_USD_PER_MILLION_TOKENS,
        {model: {"input": Decimal(input_rate), "output": Decimal(output_rate)}},
    ):
        yield


# --- Shared fixtures (mirrors test_slice4_drafting.py's pattern) -----------


class _EnvFixture:
    """Ensures GEMINI_API_KEY from the real environment never leaks into a
    "no key" test — and, for Slice 6, proves it can never trigger a call at
    all (criterion 31)."""

    def setUp(self):
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("GEMINI_API_KEY", None)

    def tearDown(self):
        self._env_patch.stop()


class _DBFixture(_EnvFixture):
    """Shared temp-SQLite-file setup for tests that touch app.db directly."""

    def setUp(self):
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = mock.patch.object(db, "DB_PATH", Path(self._tmpdir.name) / "outpost.db")
        self._db_patch.start()
        db.init()

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()
        super().tearDown()

    def _brief(self) -> Brief:
        return Brief(
            product="magnesium supplements",
            audience="distributors",
            tone="Professional",
            target_type="business",
            niche_or_industry="health & wellness distribution",
            target_countries=["United States"],
        )

    def _setup_campaign(self, name="WS") -> tuple[int, int]:
        ws = db.create_workspace(name)
        camp = db.create_campaign(ws, "promo", self._brief().model_dump_json(), "business")
        return ws, camp

    def _make_target(
        self, workspace_id, campaign_id, name="Acme Corp", handle="acme.com", fit_score=90,
    ) -> int:
        fit_reasons = [
            {"reason": "cited fact", "evidence_key": "industry", "evidence_value": "Wholesale distribution"}
        ]
        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO target (workspace_id, campaign_id, source, external_id, name,
                                     handle_or_domain, reach, location, raw_json, fit_score,
                                     fit_reasons_json, stage)
                VALUES (?, ?, 'seed', NULL, ?, ?, 10, 'United States', '{}', ?, ?, 'queued')
                """,
                (workspace_id, campaign_id, name, handle, fit_score, json.dumps(fit_reasons)),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


def _target_dict(name="Acme Corp", handle="acme.com", fit_score=90) -> dict:
    return {
        "name": name,
        "handle_or_domain": handle,
        "fit_score": fit_score,
        "fit_reasons_json": json.dumps(
            [{"reason": "cited fact", "evidence_key": "industry", "evidence_value": "Wholesale distribution"}]
        ),
    }


def _grounded_draft(target: dict) -> OutreachDraft:
    """A drafted OutreachDraft guaranteed to pass drafting._is_draft_grounded
    for `target` — names the identity and cites the target's real fit reason."""
    reasons = json.loads(target["fit_reasons_json"])
    r = reasons[0]
    return OutreachDraft(
        body=f"Hi {target['name']}, I noticed {r['evidence_value']}. Could we set up a short call?",
        evidence_key=r["evidence_key"],
        evidence_value=r["evidence_value"],
    )


def _eval_result(score: int) -> EvalResult:
    """A schema-valid EvalResult whose four dimensions sum to exactly `score`."""
    remaining = score
    points = []
    for _ in range(4):
        p = min(25, remaining)
        points.append(p)
        remaining -= p
    dims = [EvalDimension(points=p, justification="ok") for p in points]
    return EvalResult(
        rubric=EvalRubric(
            personalization=dims[0], specificity=dims[1], non_genericness=dims[2], clear_ask=dims[3]
        ),
        score=score,
    )


def _usage(model="gemini-3.6-flash", prompt=10, candidates=5, total=15, thinking=0, derived=False) -> llm.TokenUsage:
    return llm.TokenUsage(model, prompt, candidates, thinking, total, thinking_tokens_derived=derived)


class _FakeResponse:
    """A minimal httpx.Response stand-in for llm.py's own unit tests —
    only the surface llm.py actually touches (status_code, json(),
    raise_for_status())."""

    def __init__(self, status_code=200, json_body=None, json_error=False):
        self.status_code = status_code
        self._json_body = json_body
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "https://example.com"), response=self
            )


def _success_response(payload: dict, usage_meta: dict | None = None, status_code: int = 200) -> _FakeResponse:
    body = {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
    if usage_meta is not None:
        body["usageMetadata"] = usage_meta
    return _FakeResponse(status_code=status_code, json_body=body)


class _Widget(BaseModel):
    name: str


# =============================================================================
# §0.2 correction 1 — every issued attempt is recorded (criteria 1-6)
# =============================================================================


class UsageAccountingTests(_EnvFixture, unittest.TestCase):
    def test_1_no_key_produces_known_zero_and_no_request(self):
        with mock.patch("httpx.post") as post:
            result = llm.generate_structured_with_usage(_Widget, "sys", "user", {})
        post.assert_not_called()
        self.assertEqual(result, llm.MeasuredResult(None, []))

    def test_1_fully_heuristic_outreach_has_known_zero_cost(self):
        cost_tokens, estimated = routing._price([])
        self.assertEqual((cost_tokens, estimated), (0, 0))

    def test_2_transport_failure_produces_one_unknown_usage_entry(self):
        with mock.patch("httpx.post", side_effect=httpx.ConnectError("boom")):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "fake"})
        self.assertEqual(ctx.exception.usage, [llm.TokenUsage("gemini-3.6-flash", None, None, None, None)])

    def test_3a_non_2xx_without_usage_metadata_is_unknown(self):
        resp = _FakeResponse(status_code=403, json_body={"error": {"message": "denied"}})
        with mock.patch("httpx.post", return_value=resp):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "fake"})
        usage = ctx.exception.usage
        self.assertEqual(len(usage), 1)
        self.assertIsNone(usage[0].total_tokens)
        self.assertEqual(ctx.exception.kind, llm.LLMErrorKind.INVALID_KEY)

    def test_3b_non_2xx_with_usage_metadata_uses_known_fields(self):
        resp = _FakeResponse(
            status_code=500,
            json_body={
                "error": {"message": "server error"},
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3, "totalTokenCount": 10},
            },
        )
        with mock.patch("httpx.post", return_value=resp):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "fake"})
        usage = ctx.exception.usage[0]
        self.assertEqual((usage.prompt_tokens, usage.candidates_tokens, usage.total_tokens), (7, 3, 10))

    def test_4_malformed_retry_preserves_earlier_known_attempt(self):
        first = _success_response(
            {"wrong_field": "oops"},  # fails _Widget schema validation -> triggers retry
            usage_meta={"promptTokenCount": 5, "candidatesTokenCount": 2, "totalTokenCount": 7},
        )
        second = _FakeResponse(status_code=200, json_error=True)  # non-JSON body
        with mock.patch("httpx.post", side_effect=[first, second]):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "fake"})
        usage = ctx.exception.usage
        self.assertEqual(len(usage), 2)
        self.assertEqual((usage[0].prompt_tokens, usage[0].total_tokens), (5, 7))
        self.assertIsNone(usage[1].total_tokens)

    def test_5_missing_usage_metadata_is_fully_unknown(self):
        resp = _success_response({"name": "ok"})  # no usageMetadata key at all
        with mock.patch("httpx.post", return_value=resp):
            result = llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "fake"})
        self.assertEqual(len(result.usage), 1)
        u = result.usage[0]
        self.assertEqual((u.prompt_tokens, u.candidates_tokens, u.thinking_tokens, u.total_tokens), (None, None, None, None))

    def test_6_retry_preserves_both_attempts_in_order(self):
        first = _success_response(
            {"wrong": "shape"}, usage_meta={"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2}
        )
        second = _success_response(
            {"name": "ok"}, usage_meta={"promptTokenCount": 3, "candidatesTokenCount": 4, "totalTokenCount": 7}
        )
        with mock.patch("httpx.post", side_effect=[first, second]):
            result = llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "fake"})
        self.assertEqual(result.value, _Widget(name="ok"))
        self.assertEqual(len(result.usage), 2)
        self.assertEqual(result.usage[0].total_tokens, 2)
        self.assertEqual(result.usage[1].total_tokens, 7)


# =============================================================================
# §0.2 correction 2 — corrected pricing formula (criteria 7-11)
# =============================================================================


class PricingTests(unittest.TestCase):
    def test_7_rounding_boundary_below_at_above(self):
        fake_pricing = {
            "below": {"input": Decimal("0.49"), "output": Decimal("0")},
            "at": {"input": Decimal("0.50"), "output": Decimal("0")},
            "above": {"input": Decimal("0.51"), "output": Decimal("0")},
        }
        with mock.patch.object(routing, "PRICING_USD_PER_MILLION_TOKENS", fake_pricing):
            _, below = routing._price([_usage(model="below", prompt=1, total=1)])
            _, at = routing._price([_usage(model="at", prompt=1, total=1)])
            _, above = routing._price([_usage(model="above", prompt=1, total=1)])
        self.assertEqual(below, 0)
        self.assertEqual(at, 1)  # exact tie rounds up (ROUND_HALF_UP)
        self.assertEqual(above, 1)

    def test_8_default_pricing_table_is_exact_no_thinking_rate(self):
        entry = routing.PRICING_USD_PER_MILLION_TOKENS["gemini-3.6-flash"]
        self.assertEqual(set(entry.keys()), {"input", "output"})
        self.assertEqual(entry["input"], Decimal("1.50"))
        self.assertEqual(entry["output"], Decimal("7.50"))
        for rates in routing.PRICING_USD_PER_MILLION_TOKENS.values():
            self.assertNotIn("thinking", rates)

    def test_9_mixed_model_pricing_sums_exact_then_rounds_once(self):
        fake_pricing = dict(routing.PRICING_USD_PER_MILLION_TOKENS)
        fake_pricing["escalation-fake"] = {"input": Decimal("2.00"), "output": Decimal("4.00")}
        with mock.patch.object(routing, "PRICING_USD_PER_MILLION_TOKENS", fake_pricing):
            breakdown = [
                _usage(model="gemini-3.6-flash", prompt=1, total=1),  # 1 * 1.50 = 1.50
                _usage(model="escalation-fake", prompt=1, total=1),  # 1 * 2.00 = 2.00
            ]
            _, estimated = routing._price(breakdown)
        # exact sum = 3.50 -> rounds to 4, never a blended rate or per-attempt rounding
        self.assertEqual(estimated, 4)

    def test_10_invalid_entries_make_the_whole_estimate_unknown(self):
        good = _usage(model="gemini-3.6-flash", prompt=1, total=1)
        bad_total_lt_prompt = _usage(model="gemini-3.6-flash", prompt=5, total=2)
        bad_negative_prompt = llm.TokenUsage("gemini-3.6-flash", -1, 0, 0, 1)
        bad_unknown_model = _usage(model="not-a-real-model", prompt=1, total=1)
        for bad in (bad_total_lt_prompt, bad_negative_prompt, bad_unknown_model):
            _, estimated = routing._price([good, bad])
            self.assertIsNone(estimated)

    def test_11_cost_tokens_and_dollar_estimate_are_independently_unknown(self):
        usage = llm.TokenUsage("gemini-3.6-flash", None, 5, 0, 20)  # known total, unknown prompt
        cost_tokens, estimated = routing._price([usage])
        self.assertEqual(cost_tokens, 20)
        self.assertIsNone(estimated)


# =============================================================================
# §0.2 correction 3 — thinking-token derivation (criteria 12-15)
# =============================================================================


class ThinkingTokenDerivationTests(unittest.TestCase):
    def _usage_for(self, meta: dict) -> llm.TokenUsage:
        resp = _success_response({"name": "x"}, usage_meta=meta)
        return llm._extract_usage(resp, "gemini-3.6-flash")

    def test_12_inconsistent_report_without_thoughts_is_unknown(self):
        u = self._usage_for({"promptTokenCount": 10, "candidatesTokenCount": 10, "totalTokenCount": 5})
        self.assertIsNone(u.thinking_tokens)
        self.assertFalse(u.thinking_tokens_derived)

    def test_13_derived_zero_boundary(self):
        u = self._usage_for({"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15})
        self.assertEqual(u.thinking_tokens, 0)
        self.assertTrue(u.thinking_tokens_derived)

    def test_14_derived_difference_boundary(self):
        u = self._usage_for({"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 20})
        self.assertEqual(u.thinking_tokens, 5)
        self.assertTrue(u.thinking_tokens_derived)

    def test_15_provider_reported_takes_priority(self):
        u = self._usage_for(
            {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15, "thoughtsTokenCount": 99}
        )
        self.assertEqual(u.thinking_tokens, 99)
        self.assertFalse(u.thinking_tokens_derived)


# =============================================================================
# §0.2 correction 4 — routing signature fix (criteria 16-17)
# =============================================================================


class RoutingSignatureTests(_DBFixture, unittest.TestCase):
    def test_16_main_passes_workspace_scoped_paid_tier_flag(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        db.set_paid_tier_enabled(ws, True)

        captured = {}

        def fake_route(brief, target, settings, *, paid_tier_enabled):
            captured["paid_tier_enabled"] = paid_tier_enabled
            return routing.RoutingOutcome(
                body="Hi there, a captured outreach body text goes here today.",
                model_used="heuristic",
                eval_result=_eval_result(0),
                eval_status=EvalStatus.NO_GEMINI_KEY,
                cost_breakdown=[],
                cost_tokens=0,
                estimated_cost_microusd=0,
                routing_action="default",
            )

        with TestClient(app) as client, mock.patch(
            "app.main.routing.route_and_draft", side_effect=fake_route
        ):
            client.cookies.set("workspace_id", str(ws))
            client.post(f"/targets/{target_id}/draft", follow_redirects=False)

        self.assertTrue(captured["paid_tier_enabled"])

    def test_17_routing_performs_no_database_access(self):
        target = _target_dict()
        with mock.patch.object(
            db, "get_connection", side_effect=AssertionError("routing touched the database")
        ):
            outcome = routing.route_and_draft(
                self._brief(), target, {}, paid_tier_enabled=False
            )
        self.assertEqual(outcome.routing_action, "default")


# =============================================================================
# §0.2 correction 5 — header-only Gemini authentication (criteria 18-19)
# =============================================================================


class HeaderAuthTests(unittest.TestCase):
    def test_18_key_sent_only_via_header(self):
        resp = _success_response({"name": "ok"})
        with mock.patch("httpx.post", return_value=resp) as post:
            llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "test-fake-gemini-token"})
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-fake-gemini-token")

    def test_19_url_and_params_never_carry_the_key(self):
        resp = _success_response({"name": "ok"})
        with mock.patch("httpx.post", return_value=resp) as post:
            llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": "test-fake-gemini-token"})
        args, kwargs = post.call_args
        self.assertNotIn("test-fake-gemini-token", args[0])
        self.assertNotIn("params", kwargs)


# =============================================================================
# Carried forward from v2 (criteria 20-32)
# =============================================================================


class NoSilentEscalationTests(unittest.TestCase):
    def test_20_no_key_stays_on_heuristic(self):
        outcome = routing.route_and_draft(
            Brief(
                product="p", audience="a", tone="t", target_type="business",
                niche_or_industry="n", target_countries=["United States"],
            ),
            _target_dict(fit_score=100),
            {},
            paid_tier_enabled=True,
        )
        self.assertEqual(outcome.model_used, "heuristic")
        self.assertEqual(outcome.routing_action, "default")
        self.assertEqual(outcome.cost_tokens, 0)

    def test_20_key_without_opt_in_never_escalates_even_at_fit_100(self):
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(_target_dict(fit_score=100)), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
            ],
        ) as gen:
            outcome = routing.route_and_draft(
                Brief(
                    product="p", audience="a", tone="t", target_type="business",
                    niche_or_industry="n", target_countries=["United States"],
                ),
                _target_dict(fit_score=100),
                {"gemini": "fake"},
                paid_tier_enabled=False,
            )
        self.assertEqual(gen.call_count, 2)  # default draft + default eval only
        self.assertEqual(outcome.routing_action, "default")


class ThresholdInclusivityTests(unittest.TestCase):
    def _brief(self) -> Brief:
        return Brief(
            product="p", audience="a", tone="t", target_type="business",
            niche_or_industry="n", target_countries=["United States"],
        )

    def test_21_fit_84_is_not_eligible(self):
        target = _target_dict(fit_score=84)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(outcome.routing_action, "default")

    def test_21_fit_85_is_eligible(self):
        target = _target_dict(fit_score=85)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),  # below confidence -> escalates
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(90), [_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 4)
        self.assertEqual(outcome.routing_action, "escalated")

    def test_21_confidence_79_escalates_80_early_exits(self):
        target = _target_dict(fit_score=95)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(79), [_usage()]),
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(90), [_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 4)
        self.assertEqual(outcome.routing_action, "escalated")

        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(80), [_usage()]),
            ],
        ) as gen2, _escalation_enabled():
            outcome2 = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen2.call_count, 2)
        self.assertEqual(outcome2.routing_action, "early_exit")


class InvalidKeyTerminalTests(unittest.TestCase):
    def _brief(self) -> Brief:
        return Brief(
            product="p", audience="a", tone="t", target_type="business",
            niche_or_industry="n", target_countries=["United States"],
        )

    def test_22a_invalid_default_draft_is_one_call(self):
        target = _target_dict(fit_score=95)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "bad", usage=[_usage()]),
        ) as gen:
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 1)
        self.assertEqual(outcome.routing_action, "invalid_key_terminal")
        self.assertEqual(outcome.routing_detail, "default_draft")
        self.assertEqual(len(outcome.cost_breakdown), 1)

    def test_22b_invalid_default_eval_is_two_calls_no_escalation(self):
        target = _target_dict(fit_score=95)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "bad", usage=[_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(outcome.routing_action, "invalid_key_terminal")
        self.assertEqual(outcome.routing_detail, "default_eval")
        self.assertEqual(outcome.body, _grounded_draft(target).body)
        self.assertEqual(len(outcome.cost_breakdown), 2)

    def test_22c_invalid_escalated_draft_is_three_calls_no_escalated_eval(self):
        target = _target_dict(fit_score=95)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),  # below confidence -> escalate
                llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "bad", usage=[_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 3)
        self.assertEqual(outcome.routing_action, "invalid_key_terminal")
        self.assertEqual(outcome.routing_detail, "escalated_draft")
        self.assertEqual(outcome.body, _grounded_draft(target).body)  # kept the default body
        self.assertEqual(outcome.eval_result.score, 50)  # kept the default eval
        self.assertEqual(len(outcome.cost_breakdown), 3)

    def test_22d_invalid_escalated_eval_makes_no_later_call(self):
        target = _target_dict(fit_score=95)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "bad", usage=[_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 4)
        self.assertEqual(outcome.routing_action, "invalid_key_terminal")
        self.assertEqual(outcome.routing_detail, "escalated_eval")
        self.assertEqual(outcome.body, _grounded_draft(target).body)  # the escalated body is kept
        self.assertEqual(len(outcome.cost_breakdown), 4)


class EscalationUnavailableTests(unittest.TestCase):
    def test_23_escalation_model_none_is_never_silent(self):
        target = _target_dict(fit_score=95)
        brief = Brief(
            product="p", audience="a", tone="t", target_type="business",
            niche_or_industry="n", target_countries=["United States"],
        )
        self.assertIsNone(routing.ESCALATION_MODEL)  # the current, owner-gated default
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
            ],
        ) as gen:
            outcome = routing.route_and_draft(brief, target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(outcome.routing_action, "escalation_unavailable")


class EvalUniquenessTests(_DBFixture, unittest.TestCase):
    def test_24_second_eval_for_same_draft_raises(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        conn = db.get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO draft (workspace_id, target_id, body, status, model_used) "
                "VALUES (?, ?, ?, 'pending', 'heuristic')",
                (ws, target_id, "x" * 20),
            )
            draft_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO eval (workspace_id, draft_id, rubric_json, score) VALUES (?, ?, '{}', 10)",
                (ws, draft_id),
            )
            conn.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO eval (workspace_id, draft_id, rubric_json, score) VALUES (?, ?, '{}', 20)",
                    (ws, draft_id),
                )
        finally:
            conn.close()
        rows = db.get_connection()
        try:
            count = rows.execute("SELECT COUNT(*) AS c FROM eval WHERE draft_id = ?", (draft_id,)).fetchone()["c"]
        finally:
            rows.close()
        self.assertEqual(count, 1)


class AtomicRollbackTests(_DBFixture, unittest.TestCase):
    def test_25_failure_partway_leaves_no_rows(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        outcome = routing.RoutingOutcome(
            body="Hi there, an outreach body text that is long enough today.",
            model_used="heuristic",
            eval_result=_eval_result(0),
            eval_status=EvalStatus.NO_GEMINI_KEY,
            cost_breakdown=[],
            cost_tokens=0,
            estimated_cost_microusd=0,
            routing_action="default",
        )
        with mock.patch.object(audit_banners, "eval_detail", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                db.create_draft_with_routing(ws, target_id, outcome)

        self.assertEqual(len(db.list_audit(ws, camp)), 0)
        conn = db.get_connection()
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM draft").fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM eval").fetchone()["c"], 0)
        finally:
            conn.close()


class PaidTierOptInScopingTests(_DBFixture, unittest.TestCase):
    def test_26_defaults_off_and_is_workspace_scoped(self):
        ws_a, _ = self._setup_campaign("A")
        ws_b, _ = self._setup_campaign("B")
        self.assertFalse(db.get_paid_tier_enabled(ws_a))
        self.assertFalse(db.get_paid_tier_enabled(ws_b))

        db.set_paid_tier_enabled(ws_a, True)
        self.assertTrue(db.get_paid_tier_enabled(ws_a))
        self.assertFalse(db.get_paid_tier_enabled(ws_b))


class TenantIsolationTests(_DBFixture, unittest.TestCase):
    def test_27_eval_and_cost_never_cross_workspaces(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        outcome = routing.RoutingOutcome(
            body="Hi there, a tenant isolation outreach body text goes here.",
            model_used="heuristic",
            eval_result=_eval_result(50),
            eval_status=EvalStatus.NO_GEMINI_KEY,
            cost_breakdown=[],
            cost_tokens=0,
            estimated_cost_microusd=0,
            routing_action="default",
        )
        draft_id = db.create_draft_with_routing(ws_a, target_id, outcome)

        self.assertIsNone(db.get_eval_for_draft(ws_b, draft_id))
        self.assertIsNotNone(db.get_eval_for_draft(ws_a, draft_id))
        self.assertEqual(db.list_pending_drafts(ws_b), [])
        summary_b = db.outreach_cost_summary(ws_b)
        self.assertEqual(summary_b["draft_count"], 0)


class SanitizedAuditTests(_DBFixture, unittest.TestCase):
    def test_29_raw_key_never_appears_in_audit_or_cost_breakdown(self):
        """Downstream (routing/db) must never echo the raw settings key,
        regardless of what message a Gemini failure carries."""
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        secret = "not-a-real-token-fixture-value"
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "Gemini rejected the request (HTTP 403)", usage=[_usage()]),
        ):
            outcome = routing.route_and_draft(
                self._brief(), dict(db.get_target(ws, target_id)), {"gemini": secret}, paid_tier_enabled=False
            )
        draft_id = db.create_draft_with_routing(ws, target_id, outcome)
        for row in db.list_audit(ws, camp):
            self.assertNotIn(secret, row["detail"] or "")
        draft = db.get_draft(ws, draft_id)
        self.assertNotIn(secret, draft["cost_breakdown_json"] or "")

    def test_29_provider_error_message_containing_the_key_is_redacted(self):
        """llm.py's existing _safe_gemini_reason redaction still applies
        through the new usage-carrying _call_gemini path (unchanged logic,
        re-verified here since Slice 6 touched _call_gemini)."""
        key = "not-a-real-token-fixture-value2"
        resp = _FakeResponse(
            status_code=403,
            json_body={"error": {"message": f"API key {key} is invalid"}},
        )
        with mock.patch("httpx.post", return_value=resp):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured_with_usage(_Widget, "sys", "user", {"gemini": key})
        self.assertNotIn(key, ctx.exception.message)
        self.assertIn("[REDACTED]", ctx.exception.message)


class UiWordingTests(unittest.TestCase):
    def test_30_settings_hint_never_mentions_env_var(self):
        text = Path("app/templates/settings.html").read_text(encoding="utf-8")
        self.assertNotIn("GEMINI_API_KEY", text)

    def test_30_no_free_language_in_paid_tier_copy(self):
        text = Path("app/templates/settings.html").read_text(encoding="utf-8")
        # Scope the check to the paid-tier section and the corrected gemini
        # hint (§5.7) — the youtube key hint's genuinely-free quota is
        # unrelated pre-Slice-6 copy and must not fail this check.
        paid_tier_section = text.split("Stronger paid model tier")[1]
        self.assertNotIn("free", paid_tier_section.lower())
        gemini_hint = text.split('"gemini":')[1].split("\n")[0]
        self.assertNotIn("free", gemini_hint.lower())

    def test_30_no_free_language_in_cost_helper(self):
        from app.main import _cost_display

        display = _cost_display(500, 1234, json.dumps([{"model": "gemini-3.6-flash"}]))
        self.assertIn("estimated paid list-price cost", display)
        self.assertNotIn("free", display.lower())

        heuristic_display = _cost_display(0, 0, "[]")
        self.assertNotIn("free", heuristic_display.lower())


class EnvKeyCannotTriggerTests(_EnvFixture, unittest.TestCase):
    def test_31_env_key_never_triggers_drafting_eval_or_escalation(self):
        os.environ["GEMINI_API_KEY"] = "env-key-should-be-ignored"
        try:
            with mock.patch("httpx.post") as post:
                draft_result = drafting.draft_outreach(
                    Brief(
                        product="p", audience="a", tone="t", target_type="business",
                        niche_or_industry="n", target_countries=["United States"],
                    ),
                    _target_dict(),
                    {},  # no workspace key
                )
                eval_outcome = eval_mod.evaluate_draft(
                    Brief(
                        product="p", audience="a", tone="t", target_type="business",
                        niche_or_industry="n", target_countries=["United States"],
                    ),
                    _target_dict(),
                    draft_result.body,
                    {},
                )
                outcome = routing.route_and_draft(
                    Brief(
                        product="p", audience="a", tone="t", target_type="business",
                        niche_or_industry="n", target_countries=["United States"],
                    ),
                    _target_dict(fit_score=100),
                    {},
                    paid_tier_enabled=True,
                )
            post.assert_not_called()
        finally:
            os.environ.pop("GEMINI_API_KEY", None)
        self.assertEqual(draft_result.status, DraftStatus.NO_GEMINI_KEY)
        self.assertEqual(eval_outcome.status, EvalStatus.NO_GEMINI_KEY)
        self.assertEqual(outcome.routing_action, "default")
        self.assertEqual(outcome.model_used, "heuristic")


# =============================================================================
# Criterion 32 — heuristic rubric boundary tests
# =============================================================================


class HeuristicRubricTests(unittest.TestCase):
    def _target(self, name="Acme Corp", handle="acme.com", fit_reasons=None):
        if fit_reasons is None:
            fit_reasons = [{"reason": "x", "evidence_key": "industry", "evidence_value": "Wholesale distribution"}]
        return {"name": name, "handle_or_domain": handle, "fit_reasons_json": json.dumps(fit_reasons)}

    # personalization
    def test_personalization_no_identity(self):
        target = {"name": None, "handle_or_domain": None, "fit_reasons_json": "[]"}
        result = eval_mod._heuristic_eval(target, "Hi there, a message with no identity at all today.")
        self.assertEqual(result.rubric.personalization.points, 0)

    def test_personalization_present_and_referenced(self):
        target = self._target()
        result = eval_mod._heuristic_eval(target, "Hi Acme Corp, I noticed Wholesale distribution. Call?")
        self.assertEqual(result.rubric.personalization.points, 25)

    def test_personalization_present_and_not_referenced(self):
        target = self._target()
        result = eval_mod._heuristic_eval(target, "Hi there, I noticed Wholesale distribution. Call soon?")
        self.assertEqual(result.rubric.personalization.points, 0)

    # specificity
    def test_specificity_evidence_present(self):
        target = self._target()
        result = eval_mod._heuristic_eval(target, "Hi Acme Corp, I noticed Wholesale distribution. Call?")
        self.assertEqual(result.rubric.specificity.points, 25)

    def test_specificity_evidence_absent(self):
        target = self._target()
        result = eval_mod._heuristic_eval(target, "Hi Acme Corp, hope you are doing great this week. Call?")
        self.assertEqual(result.rubric.specificity.points, 0)

    def test_specificity_no_stored_reasons(self):
        target = self._target(fit_reasons=[])
        result = eval_mod._heuristic_eval(target, "Hi Acme Corp, hope you are doing great this week. Call?")
        self.assertEqual(result.rubric.specificity.points, 0)

    # non_genericness
    def test_non_genericness_all_four_combinations(self):
        target = self._target()
        no_filler_varied = "Hi Acme Corp. I noticed Wholesale distribution. Want a quick fifteen minute call this week to talk it over?"
        no_filler_uniform = "Want a call now. Want a call soon. Want a call today. Want a call please?"
        filler_varied = "Huge fan of Acme Corp! I noticed Wholesale distribution recently across the whole industry. Call?"
        filler_uniform = "Huge fan. Reaching out. Reaching out. Reaching out?"

        r1 = eval_mod._heuristic_eval(target, no_filler_varied)
        r2 = eval_mod._heuristic_eval(target, no_filler_uniform)
        r3 = eval_mod._heuristic_eval(target, filler_varied)
        r4 = eval_mod._heuristic_eval(target, filler_uniform)

        self.assertEqual(r1.rubric.non_genericness.points, 25)
        self.assertEqual(r2.rubric.non_genericness.points, 15)
        self.assertEqual(r3.rubric.non_genericness.points, 10)
        self.assertEqual(r4.rubric.non_genericness.points, 0)

    # clear_ask
    def test_clear_ask_zero_one_two_questions(self):
        target = self._target()
        zero = eval_mod._heuristic_eval(target, "Hi Acme Corp. I noticed Wholesale distribution. No ask here.")
        one = eval_mod._heuristic_eval(target, "Hi Acme Corp. I noticed Wholesale distribution. Got a minute?")
        two = eval_mod._heuristic_eval(target, "Hi Acme Corp. I noticed Wholesale distribution. Got a minute? Free Tuesday?")
        self.assertEqual(zero.rubric.clear_ask.points, 0)
        self.assertEqual(one.rubric.clear_ask.points, 25)
        self.assertEqual(two.rubric.clear_ask.points, 10)

    # missing-body defensive path
    def test_missing_body_scores_zero_everywhere(self):
        target = self._target()
        result = eval_mod._heuristic_eval(target, "   ")
        self.assertEqual(result.score, 0)
        self.assertEqual(result.rubric.personalization.points, 0)
        self.assertEqual(result.rubric.specificity.points, 0)
        self.assertEqual(result.rubric.non_genericness.points, 0)
        self.assertEqual(result.rubric.clear_ask.points, 0)

    def test_score_matches_sum_of_dimensions(self):
        target = self._target()
        result = eval_mod._heuristic_eval(target, "Hi Acme Corp, I noticed Wholesale distribution. Got a minute?")
        total = (
            result.rubric.personalization.points + result.rubric.specificity.points
            + result.rubric.non_genericness.points + result.rubric.clear_ask.points
        )
        self.assertEqual(result.score, total)


# =============================================================================
# Implementation review finding 1 — durable per-target generation reservation
# =============================================================================


class DraftGenerationReservationTests(_DBFixture, unittest.TestCase):
    def test_second_acquire_is_refused_while_first_is_active(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        first = db.try_acquire_draft_generation(ws, target_id)
        self.assertIsNotNone(first)
        second = db.try_acquire_draft_generation(ws, target_id)
        self.assertIsNone(second)

    def test_acquire_succeeds_for_the_correct_workspace_and_target(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self.assertIsNotNone(db.try_acquire_draft_generation(ws, target_id))

    def test_acquire_rejects_a_target_belonging_to_another_workspace(self):
        """The tenant-ownership check that matters: SQLite proving both IDs
        individually exist is not the same as proving the target belongs
        to the caller's workspace. A target from ws_b must not be
        reservable under ws_a, even though target_id is a real row."""
        ws_a, _camp_a = self._setup_campaign("A")
        ws_b, camp_b = self._setup_campaign("B")
        target_in_b = self._make_target(ws_b, camp_b)

        result = db.try_acquire_draft_generation(ws_a, target_in_b)

        self.assertIsNone(result)
        # And it must not have silently reserved anything under either
        # workspace/target combination.
        conn = db.get_connection()
        try:
            rows = conn.execute("SELECT * FROM draft_generation").fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 0)
        # The real owning workspace can still reserve it normally.
        self.assertIsNotNone(db.try_acquire_draft_generation(ws_b, target_in_b))

    def test_acquire_rejects_a_missing_target(self):
        ws, _camp = self._setup_campaign()
        result = db.try_acquire_draft_generation(ws, 999_999)
        self.assertIsNone(result)
        conn = db.get_connection()
        try:
            rows = conn.execute("SELECT * FROM draft_generation").fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 0)

    def test_route_never_calls_routing_when_acquisition_is_rejected(self):
        """A real request-path check: whatever the reason acquisition
        fails for, the route must never reach routing.route_and_draft."""
        from app.main import create_draft

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        workspace_row = db.get_workspace(ws)

        with mock.patch(
            "app.main.db.try_acquire_draft_generation", return_value=None
        ), mock.patch("app.main.routing.route_and_draft") as route_mock:
            create_draft(target_id, workspace=workspace_row)

        route_mock.assert_not_called()

    def test_release_allows_reacquisition(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        first = db.try_acquire_draft_generation(ws, target_id)
        db.release_draft_generation(ws, target_id, first)
        second = db.try_acquire_draft_generation(ws, target_id)
        self.assertIsNotNone(second)

    def test_cross_workspace_independence(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, camp_b = self._setup_campaign("B")
        target_a = self._make_target(ws_a, camp_a)
        target_b = self._make_target(ws_b, camp_b)
        self.assertIsNotNone(db.try_acquire_draft_generation(ws_a, target_a))
        # A different workspace's reservation is entirely independent, even
        # though nothing here shares a target id.
        self.assertIsNotNone(db.try_acquire_draft_generation(ws_b, target_b))

    def test_release_is_scoped_and_cannot_release_another_workspaces_reservation(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        reservation = db.try_acquire_draft_generation(ws_a, target_id)
        db.release_draft_generation(ws_b, target_id, reservation)  # wrong workspace -> no-op
        self.assertIsNone(db.try_acquire_draft_generation(ws_a, target_id))  # still held

    def test_expired_reservation_is_reclaimable(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        conn = db.get_connection()
        try:
            conn.execute(
                """
                INSERT INTO draft_generation (workspace_id, target_id, expires_at)
                VALUES (?, ?, datetime('now', '-10 seconds'))
                """,
                (ws, target_id),
            )
            conn.commit()
        finally:
            conn.close()
        # The stale row is already expired -- a fresh acquire must reclaim
        # it rather than treat the target as permanently blocked.
        self.assertIsNotNone(db.try_acquire_draft_generation(ws, target_id))

    def test_acquire_transaction_does_not_block_other_writers(self):
        """The acquire itself must not hold a database-wide write lock open
        across anything resembling a network call -- prove a completely
        unrelated write can proceed immediately after an acquire returns."""
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        reservation = db.try_acquire_draft_generation(ws, target_id)
        self.assertIsNotNone(reservation)
        # If the acquire's transaction were still open, this second,
        # unrelated write would hang or raise "database is locked".
        other_ws = db.create_workspace("unrelated")
        self.assertIsInstance(other_ws, int)

    def test_concurrent_requests_only_one_generates(self):
        """Two threads race to generate a draft for the same target. Only
        one may ever reach routing.route_and_draft (i.e. issue provider
        calls); the loser must be turned away before generating anything."""
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        workspace_row = db.get_workspace(ws)

        call_count = 0
        count_lock = threading.Lock()

        def fake_route(*args, **kwargs):
            nonlocal call_count
            with count_lock:
                call_count += 1
            time.sleep(0.15)  # make the race window wide and deterministic
            return routing.RoutingOutcome(
                body="Hi there, a concurrency test outreach body text today.",
                model_used="heuristic",
                eval_result=_eval_result(0),
                eval_status=EvalStatus.NO_GEMINI_KEY,
                cost_breakdown=[],
                cost_tokens=0,
                estimated_cost_microusd=0,
                routing_action="default",
            )

        barrier = threading.Barrier(2)

        def worker():
            from app.main import create_draft

            barrier.wait(timeout=5)
            create_draft(target_id, workspace=workspace_row)

        with mock.patch("app.main.routing.route_and_draft", side_effect=fake_route):
            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

        self.assertEqual(call_count, 1)
        self.assertEqual(len(db.list_pending_drafts(ws)), 1)
        # The reservation was released by the winner, so the target is not
        # left permanently blocked.
        self.assertIsNotNone(db.try_acquire_draft_generation(ws, target_id))

    def test_failed_generation_releases_the_reservation(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        workspace_row = db.get_workspace(ws)

        with mock.patch(
            "app.main.routing.route_and_draft", side_effect=RuntimeError("provider blew up")
        ):
            from app.main import create_draft

            with self.assertRaises(RuntimeError):
                create_draft(target_id, workspace=workspace_row)

        # The failure must not leave the target permanently blocked.
        reservation = db.try_acquire_draft_generation(ws, target_id)
        self.assertIsNotNone(reservation)


# =============================================================================
# Implementation review finding 2 — invalid escalated draft keeps the default
# =============================================================================


class EscalationFailurePreservesDefaultTests(unittest.TestCase):
    def _brief(self) -> Brief:
        return Brief(
            product="p", audience="a", tone="t", target_type="business",
            niche_or_industry="n", target_countries=["United States"],
        )

    def test_provider_error_during_escalated_draft_keeps_default(self):
        target = _target_dict(fit_score=95)
        default = _grounded_draft(target)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(default, [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),  # below confidence -> escalate
                llm.LLMError(llm.LLMErrorKind.ERROR, "provider boom", usage=[_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 3)  # no escalated-eval call was made
        self.assertEqual(outcome.routing_action, "escalation_failed")
        self.assertIn("gemini_error", outcome.routing_detail)
        self.assertIn("provider boom", outcome.routing_detail)
        self.assertEqual(outcome.body, default.body)
        self.assertEqual(outcome.model_used, llm.GEMINI_MODEL)  # the default model, not escalated
        self.assertEqual(outcome.eval_result.score, 50)  # the default eval, kept
        self.assertEqual(len(outcome.cost_breakdown), 3)  # the failed attempt's usage is preserved

    def test_grounding_failure_during_escalated_draft_keeps_default(self):
        target = _target_dict(fit_score=95)
        default = _grounded_draft(target)
        ungrounded = OutreachDraft(
            body="Hi there, this message does not cite the real evidence at all today.",
            evidence_key="industry",
            evidence_value="Something completely fabricated",
        )
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(default, [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
                llm.MeasuredResult(ungrounded, [_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 3)  # no escalated-eval call was made
        self.assertEqual(outcome.routing_action, "escalation_failed")
        self.assertIn("heuristic_fallback", outcome.routing_detail)
        self.assertEqual(outcome.body, default.body)
        self.assertEqual(outcome.eval_result.score, 50)
        self.assertEqual(len(outcome.cost_breakdown), 3)

    def test_invalid_key_terminal_behavior_is_unchanged(self):
        """Finding 2 must not disturb the pre-existing INVALID_GEMINI_KEY
        terminal path, which is checked first and handled separately."""
        target = _target_dict(fit_score=95)
        default = _grounded_draft(target)
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(default, [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
                llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "bad", usage=[_usage()]),
            ],
        ) as gen, _escalation_enabled():
            outcome = routing.route_and_draft(self._brief(), target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 3)
        self.assertEqual(outcome.routing_action, "invalid_key_terminal")
        self.assertEqual(outcome.routing_detail, "escalated_draft")


# =============================================================================
# Implementation review finding 3 — verified pricing required for escalation
# =============================================================================


class EscalationRequiresPricingTests(unittest.TestCase):
    def test_valid_positive_decimal_rates_are_ready(self):
        with mock.patch.object(routing, "ESCALATION_MODEL", "model-x"), mock.patch.dict(
            routing.PRICING_USD_PER_MILLION_TOKENS,
            {"model-x": {"input": Decimal("1.50"), "output": Decimal("7.50")}},
        ):
            self.assertTrue(routing._escalation_ready())

    def test_no_model_set_is_never_ready(self):
        with mock.patch.object(routing, "ESCALATION_MODEL", None):
            self.assertFalse(routing._escalation_ready())
        with mock.patch.object(routing, "ESCALATION_MODEL", ""):
            self.assertFalse(routing._escalation_ready())

    def test_missing_pricing_entry_is_never_ready(self):
        with mock.patch.object(routing, "ESCALATION_MODEL", "model-x"):
            self.assertNotIn("model-x", routing.PRICING_USD_PER_MILLION_TOKENS)
            self.assertFalse(routing._escalation_ready())

    def test_missing_input_or_output_key_is_never_ready(self):
        with mock.patch.object(routing, "ESCALATION_MODEL", "model-x"), mock.patch.dict(
            routing.PRICING_USD_PER_MILLION_TOKENS, {"model-x": {"output": Decimal("1")}}
        ):
            self.assertFalse(routing._escalation_ready())
        with mock.patch.object(routing, "ESCALATION_MODEL", "model-x"), mock.patch.dict(
            routing.PRICING_USD_PER_MILLION_TOKENS, {"model-x": {"input": Decimal("1")}}
        ):
            self.assertFalse(routing._escalation_ready())

    def test_non_decimal_values_are_never_ready(self):
        for bad in (1.5, "1.50", 1, None):
            with self.subTest(bad=bad), mock.patch.object(
                routing, "ESCALATION_MODEL", "model-x"
            ), mock.patch.dict(
                routing.PRICING_USD_PER_MILLION_TOKENS,
                {"model-x": {"input": bad, "output": Decimal("1")}},
            ):
                self.assertFalse(routing._escalation_ready())

    def test_zero_and_negative_rates_are_never_ready(self):
        for bad_value in (Decimal("0"), Decimal("-1"), Decimal("-0.01")):
            with self.subTest(bad_value=bad_value), mock.patch.object(
                routing, "ESCALATION_MODEL", "model-x"
            ), mock.patch.dict(
                routing.PRICING_USD_PER_MILLION_TOKENS,
                {"model-x": {"input": bad_value, "output": Decimal("1")}},
            ):
                self.assertFalse(routing._escalation_ready())

    def test_nan_and_infinite_rates_are_never_ready(self):
        for bad_value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.subTest(bad_value=bad_value, slot="input"), mock.patch.object(
                routing, "ESCALATION_MODEL", "model-x"
            ), mock.patch.dict(
                routing.PRICING_USD_PER_MILLION_TOKENS,
                {"model-x": {"input": bad_value, "output": Decimal("1")}},
            ):
                self.assertFalse(routing._escalation_ready())
            with self.subTest(bad_value=bad_value, slot="output"), mock.patch.object(
                routing, "ESCALATION_MODEL", "model-x"
            ), mock.patch.dict(
                routing.PRICING_USD_PER_MILLION_TOKENS,
                {"model-x": {"input": Decimal("1"), "output": bad_value}},
            ):
                self.assertFalse(routing._escalation_ready())

    def test_invalid_pricing_never_escalates_at_the_routing_level(self):
        """Routing-level assertion: invalid pricing (Decimal("NaN")) makes
        escalation unavailable, and only the default draft/eval calls are
        made -- an escalation attempt never happens."""
        target = _target_dict(fit_score=95)
        brief = Brief(
            product="p", audience="a", tone="t", target_type="business",
            niche_or_industry="n", target_countries=["United States"],
        )
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
            ],
        ) as gen, mock.patch.object(routing, "ESCALATION_MODEL", "nan-priced-model"), mock.patch.dict(
            routing.PRICING_USD_PER_MILLION_TOKENS,
            {"nan-priced-model": {"input": Decimal("NaN"), "output": Decimal("1")}},
        ):
            outcome = routing.route_and_draft(brief, target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(outcome.routing_action, "escalation_unavailable")

    def test_escalation_model_without_pricing_entry_never_escalates(self):
        """Setting only ESCALATION_MODEL, with no matching pricing entry,
        must not let a paid escalation call through."""
        target = _target_dict(fit_score=95)
        brief = Brief(
            product="p", audience="a", tone="t", target_type="business",
            niche_or_industry="n", target_countries=["United States"],
        )
        with mock.patch(
            "app.llm.generate_structured_with_usage",
            side_effect=[
                llm.MeasuredResult(_grounded_draft(target), [_usage()]),
                llm.MeasuredResult(_eval_result(50), [_usage()]),
            ],
        ) as gen, mock.patch.object(routing, "ESCALATION_MODEL", "unpriced-model-fake"):
            self.assertNotIn("unpriced-model-fake", routing.PRICING_USD_PER_MILLION_TOKENS)
            outcome = routing.route_and_draft(brief, target, {"gemini": "fake"}, paid_tier_enabled=True)
        self.assertEqual(gen.call_count, 2)  # default draft + default eval only
        self.assertEqual(outcome.routing_action, "escalation_unavailable")


# =============================================================================
# Implementation review finding 4 — Approvals cost-summary visibility
# =============================================================================


class ApprovalsCostSummaryTests(_DBFixture, unittest.TestCase):
    def _insert_draft(self, ws, target_id, status, cost_tokens, estimated_cost_microusd):
        conn = db.get_connection()
        try:
            conn.execute(
                """
                INSERT INTO draft (workspace_id, target_id, body, status, model_used,
                                    cost_tokens, cost_breakdown_json, estimated_cost_microusd)
                VALUES (?, ?, ?, ?, 'heuristic', ?, '[]', ?)
                """,
                (ws, target_id, "x" * 25, status, cost_tokens, estimated_cost_microusd),
            )
            conn.commit()
        finally:
            conn.close()

    def _approvals_html(self, ws) -> str:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws))
            resp = client.get("/approvals")
        return resp.text

    def test_historical_drafts_with_empty_pending_queue_still_show_summary(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._insert_draft(ws, target_id, "approved", 1000, 5_000_000)
        html = self._approvals_html(ws)
        self.assertIn("cost-summary", html)
        self.assertIn("$5.0000", html)
        self.assertIn("No drafts waiting for review", html)  # the queue itself is still empty

    def test_all_costs_unknown_shows_unknown_wording_and_excluded_count(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._insert_draft(ws, target_id, "rejected", None, None)
        html = self._approvals_html(ws)
        self.assertIn("No outreach with a known cost yet.", html)
        self.assertIn("1 excluded", html)

    def test_mixed_known_and_unknown_costs(self):
        ws, camp = self._setup_campaign()
        t1 = self._make_target(ws, camp, name="A", handle="a.com")
        t2 = self._make_target(ws, camp, name="B", handle="b.com")
        self._insert_draft(ws, t1, "approved", 1000, 2_000_000)
        self._insert_draft(ws, t2, "rejected", None, None)
        html = self._approvals_html(ws)
        self.assertIn("$2.0000", html)
        self.assertIn("1 excluded", html)

    def test_known_heuristic_zero_cost_outreach(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._insert_draft(ws, target_id, "approved", 0, 0)
        html = self._approvals_html(ws)
        self.assertIn("$0.0000", html)
        self.assertNotIn("excluded", html)

    def test_no_drafts_at_all_shows_no_summary(self):
        ws, _camp = self._setup_campaign()
        html = self._approvals_html(ws)
        self.assertNotIn("cost-summary", html)


if __name__ == "__main__":
    unittest.main()
