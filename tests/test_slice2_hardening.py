"""Maintained regression tests for the Slice 2 hardening pass.

These are retained tests (unittest, no third-party test dependency), not a
disposable verification script. They:

- never call a paid service (every httpx call is mocked),
- never use a real credential (only obviously-fake placeholder keys),
- never touch the real outpost.db (a temporary SQLite file is used),
- never mutate the real seed file (a temporary seeds dir is used).

Run: python -m unittest tests.test_slice2_hardening -v
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from app import audit_banners, db, llm, sources
from app.agent import intake
from app.agent.intake import IntakeStatus
from app.models import Brief
from app.sources.apollo import ApolloSource
from app.sources.base import SourceStatus
from app.sources.seed import SeedSource

FAKE_GEMINI_KEY = "fake-gemini-key-not-a-real-credential"
FAKE_APOLLO_KEY = "fake-apollo-key-not-a-real-credential"

_UNSET = object()


def _business_brief() -> Brief:
    return Brief(
        product="Magnesium supplements",
        audience="Distributors",
        tone="Professional",
        target_type="business",
        niche_or_industry="wellness",
        target_countries=["United States"],
    )


class FakeResponse:
    """A minimal stand-in for httpx.Response, enough for the code under test."""

    def __init__(self, status_code, json_data=_UNSET, json_error=False, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error
        self.text = text

    def json(self):
        if self._json_error or self._json_data is _UNSET:
            raise json.JSONDecodeError("Expecting value", "", 0)
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "https://example.test"),
                response=self,
            )


def _gemini_ok(text: str) -> FakeResponse:
    """A well-formed Gemini 200 whose single text part is `text`."""
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


_VALID_PARSED = json.dumps(
    {"product": "P", "audience": "A", "tone": "T", "niche_or_industry": "N"}
)


class GeminiFailureTests(unittest.TestCase):
    """Correction 1: every Gemini response failure becomes LLMError, never a raw exception."""

    def _assert_llmerror(self, response_or_side_effect):
        with mock.patch("app.llm.httpx.post") as post:
            if isinstance(response_or_side_effect, list):
                post.side_effect = response_or_side_effect
            else:
                post.return_value = response_or_side_effect
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured(
                    intake._ParsedFields, "sys", "user", {"gemini": FAKE_GEMINI_KEY}
                )
            return ctx.exception

    def test_non_json_200_becomes_llmerror(self):
        exc = self._assert_llmerror(FakeResponse(200, json_error=True))
        self.assertEqual(exc.kind, llm.LLMErrorKind.ERROR)

    def test_empty_candidates_becomes_llmerror(self):
        exc = self._assert_llmerror(FakeResponse(200, {"candidates": []}))
        self.assertEqual(exc.kind, llm.LLMErrorKind.ERROR)

    def test_missing_content_or_parts_becomes_llmerror(self):
        exc = self._assert_llmerror(FakeResponse(200, {"candidates": [{"content": {}}]}))
        self.assertEqual(exc.kind, llm.LLMErrorKind.ERROR)

    def test_part_without_usable_text_becomes_llmerror(self):
        body = {"candidates": [{"content": {"parts": [{"inlineData": "x"}]}}]}
        exc = self._assert_llmerror(FakeResponse(200, body))
        self.assertEqual(exc.kind, llm.LLMErrorKind.ERROR)

    def test_model_output_failing_validation_twice_becomes_llmerror(self):
        bad = _gemini_ok('{"unexpected": "shape"}')
        # Two calls (first attempt + corrective retry), both return bad output.
        exc = self._assert_llmerror([bad, bad])
        self.assertEqual(exc.kind, llm.LLMErrorKind.ERROR)

    def test_network_error_reason_has_no_url_or_key(self):
        with mock.patch("app.llm.httpx.post", side_effect=httpx.ConnectError("boom")):
            with self.assertRaises(llm.LLMError) as ctx:
                llm.generate_structured(
                    intake._ParsedFields, "sys", "user", {"gemini": FAKE_GEMINI_KEY}
                )
        self.assertNotIn(FAKE_GEMINI_KEY, ctx.exception.message)
        self.assertNotIn("http", ctx.exception.message.lower())

    def test_provider_error_message_redacts_gemini_key(self):
        response = FakeResponse(
            403,
            {"error": {"message": f"credential {FAKE_GEMINI_KEY} was rejected"}},
        )
        exc = self._assert_llmerror(response)
        self.assertNotIn(FAKE_GEMINI_KEY, exc.message)
        self.assertIn("[REDACTED]", exc.message)

class IntakeFallbackTests(unittest.TestCase):
    """Correction 1: intake degrades to the heuristic with GEMINI_ERROR."""

    def test_gemini_error_falls_back_with_status_and_valid_brief(self):
        with mock.patch("app.llm.httpx.post", return_value=FakeResponse(200, json_error=True)):
            result = intake.parse_brief(
                "US distributors for magnesium", "business", {"gemini": FAKE_GEMINI_KEY}
            )
        self.assertEqual(result.status, IntakeStatus.GEMINI_ERROR)
        self.assertEqual(result.brief.target_type, "business")
        self.assertTrue(result.brief.product)  # a valid heuristic Brief was produced
        # A rejected credential (403) is classified distinctly from a generic error.
        with mock.patch(
            "app.llm.httpx.post",
            return_value=FakeResponse(403, {"error": {"message": "denied"}}),
        ):
            rejected = intake.parse_brief("x", "business", {"gemini": FAKE_GEMINI_KEY})
        self.assertEqual(rejected.status, IntakeStatus.INVALID_GEMINI_KEY)

    def test_error_reason_never_contains_the_key(self):
        with mock.patch("app.llm.httpx.post", return_value=FakeResponse(200, json_error=True)):
            result = intake.parse_brief("x", "business", {"gemini": FAKE_GEMINI_KEY})
        self.assertNotIn(FAKE_GEMINI_KEY, result.reason or "")


class GeminiSchemaTests(unittest.TestCase):
    """Correction 2: the request body carries the provider-side response schema."""

    def test_request_body_includes_response_json_schema(self):
        with mock.patch("app.llm.httpx.post", return_value=_gemini_ok(_VALID_PARSED)) as post:
            parsed = llm.generate_structured(
                intake._ParsedFields, "sys", "user", {"gemini": FAKE_GEMINI_KEY}
            )
        self.assertIsNotNone(parsed)
        sent = post.call_args.kwargs["json"]
        gen_config = sent["generationConfig"]
        self.assertEqual(gen_config["responseMimeType"], "application/json")
        expected = llm._response_schema(intake._ParsedFields)
        self.assertEqual(gen_config["responseJsonSchema"], expected)
        # Derived from the Pydantic schema, with unsupported keywords stripped.
        self.assertIn("properties", gen_config["responseJsonSchema"])
        self.assertNotIn("default", json.dumps(gen_config["responseJsonSchema"]))


class ApolloClassificationTests(unittest.TestCase):
    """Correction 3: HTTP status classification is not "everything is a bad key"."""

    def _search(self, response=None, side_effect=None):
        with mock.patch("app.sources.apollo.httpx.post") as post:
            if side_effect is not None:
                post.side_effect = side_effect
            else:
                post.return_value = response
            return ApolloSource(FAKE_APOLLO_KEY).search(_business_brief())

    def test_200_valid_payload_is_ok(self):
        body = {"organizations": [{"id": 1, "name": "Acme", "primary_domain": "acme.com"}]}
        result = self._search(FakeResponse(200, body))
        self.assertEqual(result.status, SourceStatus.OK)
        self.assertEqual(len(result.candidates), 1)

    def test_401_is_invalid_key(self):
        result = self._search(FakeResponse(401, {"error": "unauthorized"}))
        self.assertEqual(result.status, SourceStatus.INVALID_KEY)

    def test_403_is_insufficient_plan(self):
        result = self._search(FakeResponse(403, {"error": "not in your Free plan"}))
        self.assertEqual(result.status, SourceStatus.INSUFFICIENT_PLAN)

    def test_429_is_rate_limited(self):
        result = self._search(FakeResponse(429, {"error": "rate limit exceeded"}))
        self.assertEqual(result.status, SourceStatus.RATE_LIMITED)

    def test_422_is_provider_error(self):
        result = self._search(FakeResponse(422, {"error": "unprocessable"}))
        self.assertEqual(result.status, SourceStatus.PROVIDER_ERROR)

    def test_500_is_provider_error(self):
        result = self._search(FakeResponse(500, {"error": "server error"}))
        self.assertEqual(result.status, SourceStatus.PROVIDER_ERROR)

    def test_malformed_200_is_provider_error_without_raising(self):
        # organizations is not a list.
        result = self._search(FakeResponse(200, {"organizations": "nope"}))
        self.assertEqual(result.status, SourceStatus.PROVIDER_ERROR)
        self.assertEqual(result.candidates, [])
        # Non-JSON 200 body.
        result2 = self._search(FakeResponse(200, json_error=True))
        self.assertEqual(result2.status, SourceStatus.PROVIDER_ERROR)

    def test_network_error_is_network_error(self):
        result = self._search(side_effect=httpx.ConnectTimeout("timed out"))
        self.assertEqual(result.status, SourceStatus.NETWORK_ERROR)

    def test_reason_is_sanitized_and_keyless(self):
        # A dict-valued "error" must NOT be stringified into the reason.
        result = self._search(FakeResponse(403, {"error": {"secret": "payload"}}))
        self.assertNotIn("secret", result.reason)
        self.assertNotIn("payload", result.reason)
        self.assertNotIn(FAKE_APOLLO_KEY, result.reason)
        self.assertIn("403", result.reason)

        # A string-valued provider message must redact an echoed credential.
        echoed = self._search(
            FakeResponse(401, {"error": f"credential {FAKE_APOLLO_KEY} was rejected"})
        )
        self.assertNotIn(FAKE_APOLLO_KEY, echoed.reason)
        self.assertIn("[REDACTED]", echoed.reason)

class SeedSourceTests(unittest.TestCase):
    """Correction 4: SeedSource returns a typed failure, never raises."""

    def test_invalid_utf8_is_seed_error(self):
        self.assertEqual(self._seed_with(b"\xff\xfe\x80").status, SourceStatus.SEED_ERROR)

    def _seed_with(self, contents: str | bytes | None):
        with tempfile.TemporaryDirectory() as tmp:
            seeds_dir = Path(tmp)
            if isinstance(contents, bytes):
                (seeds_dir / "companies.json").write_bytes(contents)
            elif contents is not None:
                (seeds_dir / "companies.json").write_text(contents, encoding="utf-8")
            with mock.patch("app.sources.seed.SEEDS_DIR", seeds_dir):
                return SeedSource("business").search(_business_brief())

    def test_missing_file_is_seed_error(self):
        self.assertEqual(self._seed_with(None).status, SourceStatus.SEED_ERROR)

    def test_invalid_json_is_seed_error(self):
        self.assertEqual(self._seed_with("not json").status, SourceStatus.SEED_ERROR)

    def test_unexpected_top_level_shape_is_seed_error(self):
        self.assertEqual(self._seed_with("{}").status, SourceStatus.SEED_ERROR)

    def test_malformed_row_is_seed_error(self):
        # Row survives the country filter but is missing the required name field.
        malformed = '[{"country": "United States", "no_name": 1}]'
        self.assertEqual(self._seed_with(malformed).status, SourceStatus.SEED_ERROR)

    def test_valid_seed_data_is_ok(self):
        good = json.dumps(
            [{"name": "X Co", "domain": "x.co", "employees": 100, "country": "United States"}]
        )
        result = self._seed_with(good)
        self.assertEqual(result.status, SourceStatus.OK)
        self.assertEqual(len(result.candidates), 1)


class DiscoverFallbackTests(unittest.TestCase):
    """Correction 4: a failed seed fallback does not claim seed data was shown."""

    def test_seed_fallback_failure_reports_seed_error_with_no_candidates(self):
        # No Apollo key → seed is the primary source; force seed to fail.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("app.sources.seed.SEEDS_DIR", Path(tmp)):  # empty dir → missing file
                result = sources.discover(_business_brief(), settings={})
        self.assertEqual(result.status, SourceStatus.SEED_ERROR)
        self.assertEqual(result.candidates, [])
        # The banner copy for this status must not blame the key or claim results.
        _, severity, template = audit_banners.DISCOVERY_MAP[SourceStatus.SEED_ERROR]
        self.assertEqual(severity, "warning")
        self.assertIn("No results", template)


class BannerCopyTests(unittest.TestCase):
    """Correction 3: rate-limit and provider-error copy advises the owner accurately."""

    def test_rate_limit_copy_does_not_tell_owner_to_replace_key(self):
        action, severity, template = audit_banners.DISCOVERY_MAP[SourceStatus.RATE_LIMITED]
        self.assertEqual(action, "discovery.rate_limited")
        self.assertNotIn("check your Apollo key", template)
        self.assertIn("seed data", template.lower())

    def test_provider_error_copy_does_not_blame_key(self):
        action, severity, template = audit_banners.DISCOVERY_MAP[SourceStatus.PROVIDER_ERROR]
        self.assertEqual(action, "discovery.provider_error")
        self.assertIn("not your key", template)
        self.assertIn("seed data", template.lower())


class _TempDbTestCase(unittest.TestCase):
    """Base: an isolated temp DB and a guaranteed-absent GEMINI_API_KEY."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = mock.patch.object(db, "DB_PATH", Path(self._tmpdir.name) / "outpost.db")
        self._db_patch.start()
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("GEMINI_API_KEY", None)  # guarantee the zero-key path
        db.init()

    def tearDown(self):
        self._env_patch.stop()
        self._db_patch.stop()
        self._tmpdir.cleanup()


class CampaignFormValidationTests(_TempDbTestCase):
    """Correction 5: bad form input is a controlled 4xx, never a 500."""

    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from app.main import app

        self._client_ctx = TestClient(app)
        self.client = self._client_ctx.__enter__()
        self.workspace_id = db.create_workspace("Test WS")
        self.client.cookies.set("workspace_id", str(self.workspace_id))

    def tearDown(self):
        self._client_ctx.__exit__(None, None, None)
        super().tearDown()

    def test_invalid_target_type_returns_422_not_500(self):
        resp = self.client.post(
            "/campaigns",
            data={"promoting_what": "x", "target_type": "banana"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 422)

    def test_empty_promoting_what_returns_4xx(self):
        resp = self.client.post(
            "/campaigns",
            data={"promoting_what": "   ", "target_type": "business"},
            follow_redirects=False,
        )
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertLess(resp.status_code, 500)

    def test_valid_zero_key_campaign_creates_six_us_seed_targets(self):
        resp = self.client.post(
            "/campaigns",
            data={"promoting_what": "US distributors for magnesium", "target_type": "business"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        campaign_id = int(resp.headers["location"].rsplit("/", 1)[1])
        targets = db.list_targets(self.workspace_id, campaign_id)
        self.assertEqual(len(targets), 6)
        self.assertTrue(all(t["source"] == "seed" for t in targets))
        self.assertTrue(all(json.loads(t["raw_json"])["country"] == "United States" for t in targets))
        actions = {row["action"] for row in db.list_audit(self.workspace_id, campaign_id)}
        self.assertIn("intake.no_gemini_key", actions)
        self.assertIn("discovery.no_apollo_key", actions)


class TenantIsolationTests(_TempDbTestCase):
    """Correction: multi-tenant isolation of campaign/target/audit rows."""

    def test_targets_and_audit_are_scoped_per_workspace(self):
        ws_a = db.create_workspace("Alpha")
        ws_b = db.create_workspace("Beta")
        camp_a = db.create_campaign(ws_a, "a", _business_brief().model_dump_json(), "business")
        camp_b = db.create_campaign(ws_b, "b", _business_brief().model_dump_json(), "business")

        seed = SeedSource("business").search(_business_brief())
        db.add_targets(ws_a, camp_a, seed.candidates, "seed")
        db.add_audit(ws_a, camp_a, "agent", "discovery.no_apollo_key")

        # Workspace B sees none of A's rows.
        self.assertEqual(db.list_targets(ws_b, camp_b), [])
        self.assertEqual(db.list_audit(ws_b, camp_b), [])
        self.assertEqual(len(db.list_targets(ws_a, camp_a)), len(seed.candidates))
        # A target id from A is invisible when queried under B's campaign.
        self.assertEqual(db.list_targets(ws_b, camp_a), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
