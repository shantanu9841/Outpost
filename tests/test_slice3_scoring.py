"""Maintained regression tests for Slice 3 (fit-scoring with citations).

Retained unittest tests, not disposable scripts (SLICE_3_PLAN.md correction
6). Every Gemini call is mocked at app.llm.generate_structured — no real
provider call, no real key, no outpost.db writes (a temporary SQLite file is
used wherever a DB is touched).

Run: python -m unittest tests.test_slice3_scoring -v
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx
from pydantic import ValidationError

from app import db, llm
from app.agent import scoring
from app.agent.intake import IntakeStatus
from app.agent.scoring import ScoreStatus, TargetScore, _heuristic, _is_grounded, _stem
from app.models import Brief, Candidate, FitAssessment, FitBatch, FitReason
from app.sources.apollo import normalize_evidence as apollo_normalize_evidence
from app.sources.base import SourceResult, SourceStatus, coerce_int
from app.sources.seed import normalize_evidence as seed_normalize_evidence


def _canonical_brief() -> Brief:
    """The canonical test brief anchoring SLICE_3_PLAN.md §4.3's score table."""
    return Brief(
        product="magnesium supplements",
        audience="distributors",
        tone="Professional",
        target_type="business",
        niche_or_industry="health & wellness distribution",
        target_countries=["United States"],
    )


# Normalized evidence for the seed companies in §4.3's anchor table.
CORNERSTONE = {
    "name": "Cornerstone Wellness Distributors",
    "industry": "Health & wellness distribution",
    "employees": 75,
    "country": "United States",
    "domain": "cornerstonewellness.com",
}
MERIDIAN = {
    "name": "Meridian Health Supply",
    "industry": "Health & wellness distribution",
    "employees": 95,
    "country": "United States",
    "domain": "meridianhealthsupply.com",
}
NORTHBRIDGE = {
    "name": "Northbridge Distribution Co.",
    "industry": "Wholesale distribution",
    "employees": 180,
    "country": "United States",
    "domain": "northbridgedist.com",
}
CASCADE = {
    "name": "Cascade Logistics Partners",
    "industry": "Third-party logistics",
    "employees": 340,
    "country": "United States",
    "domain": "cascadelogistics.com",
}
IRONCLAD = {
    "name": "Ironclad Freight Solutions",
    "industry": "Freight & logistics",
    "employees": 520,
    "country": "United States",
    "domain": "ironcladfreight.com",
}
SUMMIT = {
    "name": "Summit Supply Chain Group",
    "industry": "Supply chain services",
    "employees": 410,
    "country": "United States",
    "domain": "summitsupplychain.com",
}
LAKESIDE = {
    "name": "Lakeside Software Studio",
    "industry": "Consumer mobile apps",
    "employees": 12,
    "country": "United States",
    "domain": "lakesidesoftware.io",
}


def _two_target_evidence() -> list[dict]:
    return [
        {
            "name": "Target A",
            "industry": "Wholesale distribution",
            "employees": 200,
            "country": "United States",
            "domain": "a.com",
        },
        {
            "name": "Target B",
            "industry": "Consumer apps",
            "employees": 10,
            "country": "United States",
            "domain": "b.com",
        },
    ]


class SchemaShapeTests(unittest.TestCase):
    """Test 1: the schema enforces shape (non-blank fields, >=1 reason, 0-100)."""

    def test_fit_reason_rejects_blank_fields(self):
        with self.assertRaises(ValidationError):
            FitReason(reason="", evidence_key="employees", evidence_value="10")
        with self.assertRaises(ValidationError):
            FitReason(reason="ok", evidence_key="   ", evidence_value="10")
        with self.assertRaises(ValidationError):
            FitReason(reason="ok", evidence_key="employees", evidence_value="")

    def test_fit_assessment_rejects_empty_reasons(self):
        with self.assertRaises(ValidationError):
            FitAssessment(target_index=0, fit_score=50, reasons=[])

    def test_fit_assessment_rejects_out_of_range_score(self):
        reason = FitReason(reason="ok", evidence_key="employees", evidence_value="10")
        with self.assertRaises(ValidationError):
            FitAssessment(target_index=0, fit_score=101, reasons=[reason])
        with self.assertRaises(ValidationError):
            FitAssessment(target_index=0, fit_score=-1, reasons=[reason])


class GroundingTests(unittest.TestCase):
    """Test 2: _is_grounded checks truth, not just shape."""

    def test_matching_citation_is_grounded(self):
        evidence = {"employees": 180}
        reason = FitReason(reason="ok", evidence_key="employees", evidence_value="180")
        self.assertTrue(_is_grounded(reason, evidence))

    def test_missing_key_is_not_grounded(self):
        evidence = {"employees": 180}
        reason = FitReason(reason="ok", evidence_key="revenue", evidence_value="1000000")
        self.assertFalse(_is_grounded(reason, evidence))

    def test_mismatched_integer_value_is_not_grounded(self):
        evidence = {"employees": 180}
        reason = FitReason(reason="ok", evidence_key="employees", evidence_value="999")
        self.assertFalse(_is_grounded(reason, evidence))

    def test_mismatched_string_value_is_not_grounded(self):
        evidence = {"country": "United States"}
        reason = FitReason(reason="ok", evidence_key="country", evidence_value="Germany")
        self.assertFalse(_is_grounded(reason, evidence))

    def test_none_evidence_value_is_not_grounded_even_though_key_exists(self):
        # Correction: a key that exists but carries None must not ground a
        # citation — e.g. a fabricated "country: None" claim.
        evidence = {"country": None}
        reason = FitReason(reason="ok", evidence_key="country", evidence_value="None")
        self.assertFalse(_is_grounded(reason, evidence))

    def test_blank_evidence_value_is_not_grounded(self):
        evidence = {"industry": "   "}
        reason = FitReason(reason="ok", evidence_key="industry", evidence_value="Some Industry")
        self.assertFalse(_is_grounded(reason, evidence))


class HeuristicAnchorTests(unittest.TestCase):
    """Test 3: the canonical brief reproduces SLICE_3_PLAN.md §4.3's exact totals."""

    def test_anchor_scores_match_table(self):
        brief = _canonical_brief()
        cases = [
            (CORNERSTONE, 90),
            (MERIDIAN, 90),
            (NORTHBRIDGE, 60),
            (CASCADE, 40),
            (IRONCLAD, 40),
            (SUMMIT, 40),
            (LAKESIDE, 20),
        ]
        for evidence, expected in cases:
            score, reasons = _heuristic(brief, evidence)
            self.assertEqual(score, expected, evidence["name"])
            self.assertTrue(reasons)
            for reason in reasons:
                self.assertTrue(_is_grounded(reason, evidence), f"{evidence['name']}: {reason}")

    def test_weak_seed_is_low_and_strong_seeds_are_high(self):
        brief = _canonical_brief()
        weak_score, _ = _heuristic(brief, LAKESIDE)
        strong_score, _ = _heuristic(brief, CORNERSTONE)
        self.assertLess(weak_score, 70)
        self.assertGreaterEqual(strong_score, 85)


class NormalizationTests(unittest.TestCase):
    """Test 4: Apollo and seed rows both normalize to the same evidence shape."""

    def test_apollo_row_normalizes_employees_field(self):
        raw = {
            "name": "Acme",
            "industry": "Retail",
            "estimated_num_employees": 180,
            "country": "United States",
            "primary_domain": "acme.com",
        }
        self.assertEqual(apollo_normalize_evidence(raw)["employees"], 180)

    def test_seed_row_normalizes_employees_field(self):
        raw = {
            "name": "Acme",
            "industry": "Retail",
            "employees": 180,
            "country": "United States",
            "domain": "acme.com",
        }
        self.assertEqual(seed_normalize_evidence(raw)["employees"], 180)

    def test_both_sources_produce_the_identical_shape(self):
        apollo_raw = {
            "name": "A", "industry": "I", "estimated_num_employees": 50,
            "country": "C", "primary_domain": "d.com",
        }
        seed_raw = {"name": "A", "industry": "I", "employees": 50, "country": "C", "domain": "d.com"}
        self.assertEqual(apollo_normalize_evidence(apollo_raw), seed_normalize_evidence(seed_raw))


class BatchAggregationTests(unittest.TestCase):
    """Tests 5 & 6: honest per-target fallback for ungrounded/missing/duplicate/out-of-range."""

    def test_ungrounded_citation_falls_back_only_that_target(self):
        evidence_list = _two_target_evidence()
        batch = FitBatch(
            assessments=[
                FitAssessment(
                    target_index=0, fit_score=95,
                    reasons=[FitReason(reason="great fit", evidence_key="employees", evidence_value="200")],
                ),
                FitAssessment(
                    target_index=1, fit_score=80,
                    # Fabricated: evidence["employees"] is 10, not 500.
                    reasons=[FitReason(reason="fabricated", evidence_key="employees", evidence_value="500")],
                ),
            ]
        )
        with mock.patch("app.llm.generate_structured", return_value=batch):
            outcome = scoring.score_batch(_canonical_brief(), evidence_list, {"gemini": "fake"})
        self.assertEqual(outcome.status, ScoreStatus.PARTIAL_HEURISTIC)
        self.assertEqual(outcome.llm_scored, 1)
        self.assertEqual(outcome.heuristic_scored, 1)
        self.assertEqual(outcome.scores[0].scored_by, "llm")
        self.assertEqual(outcome.scores[1].scored_by, "heuristic")
        self.assertIn("1 of 2", outcome.reason)

    def test_missing_target_index_falls_back(self):
        evidence_list = _two_target_evidence()
        # Only target 0 is present; target 1 is entirely absent from the batch.
        batch = FitBatch(
            assessments=[
                FitAssessment(
                    target_index=0, fit_score=95,
                    reasons=[FitReason(reason="great fit", evidence_key="employees", evidence_value="200")],
                ),
            ]
        )
        with mock.patch("app.llm.generate_structured", return_value=batch):
            outcome = scoring.score_batch(_canonical_brief(), evidence_list, {"gemini": "fake"})
        self.assertEqual(outcome.scores[0].scored_by, "llm")
        self.assertEqual(outcome.scores[1].scored_by, "heuristic")
        self.assertEqual(outcome.heuristic_scored, 1)

    def test_duplicate_target_index_ignores_the_extra(self):
        evidence_list = _two_target_evidence()
        batch = FitBatch(
            assessments=[
                FitAssessment(
                    target_index=0, fit_score=95,
                    reasons=[FitReason(reason="first", evidence_key="employees", evidence_value="200")],
                ),
                FitAssessment(
                    target_index=0, fit_score=10,
                    reasons=[FitReason(reason="duplicate", evidence_key="employees", evidence_value="200")],
                ),
            ]
        )
        with mock.patch("app.llm.generate_structured", return_value=batch):
            outcome = scoring.score_batch(_canonical_brief(), evidence_list, {"gemini": "fake"})
        # Target 0 uses the first-seen assessment; target 1, covered by no
        # assessment at all, falls back to the heuristic.
        self.assertEqual(outcome.scores[0].fit_score, 95)
        self.assertEqual(outcome.scores[0].scored_by, "llm")
        self.assertEqual(outcome.scores[1].scored_by, "heuristic")

    def test_out_of_range_target_index_is_dropped(self):
        evidence_list = _two_target_evidence()
        batch = FitBatch(
            assessments=[
                FitAssessment(
                    target_index=5, fit_score=95,
                    reasons=[FitReason(reason="out of range", evidence_key="employees", evidence_value="200")],
                ),
                FitAssessment(
                    target_index=-1, fit_score=50,
                    reasons=[FitReason(reason="negative", evidence_key="employees", evidence_value="200")],
                ),
            ]
        )
        with mock.patch("app.llm.generate_structured", return_value=batch):
            outcome = scoring.score_batch(_canonical_brief(), evidence_list, {"gemini": "fake"})
        # Neither out-of-range assessment applies to any real target, so both
        # of the two real targets fall back to the heuristic.
        self.assertEqual(outcome.heuristic_scored, 2)
        self.assertEqual(outcome.status, ScoreStatus.PARTIAL_HEURISTIC)


class ScoreBatchFallbackTests(unittest.TestCase):
    """Test 7: terminal credential failure is a single call, never a retry loop."""

    def test_no_key_scores_all_heuristic(self):
        with mock.patch("app.llm.generate_structured", return_value=None):
            outcome = scoring.score_batch(_canonical_brief(), _two_target_evidence(), {})
        self.assertEqual(outcome.status, ScoreStatus.NO_GEMINI_KEY)
        self.assertEqual(outcome.heuristic_scored, 2)
        self.assertEqual(outcome.llm_scored, 0)

    def test_invalid_key_scores_all_heuristic_and_calls_llm_exactly_once(self):
        with mock.patch(
            "app.llm.generate_structured",
            side_effect=llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "credential rejected"),
        ) as mocked:
            outcome = scoring.score_batch(_canonical_brief(), _two_target_evidence(), {"gemini": "fake"})
        self.assertEqual(outcome.status, ScoreStatus.INVALID_GEMINI_KEY)
        self.assertEqual(outcome.heuristic_scored, 2)
        self.assertEqual(outcome.llm_scored, 0)
        self.assertEqual(mocked.call_count, 1)

    def test_other_llm_error_scores_all_heuristic(self):
        with mock.patch(
            "app.llm.generate_structured",
            side_effect=llm.LLMError(llm.LLMErrorKind.ERROR, "network blip"),
        ):
            outcome = scoring.score_batch(_canonical_brief(), _two_target_evidence(), {"gemini": "fake"})
        self.assertEqual(outcome.status, ScoreStatus.GEMINI_ERROR)
        self.assertEqual(outcome.heuristic_scored, 2)

    def test_empty_evidence_list_returns_empty_outcome(self):
        outcome = scoring.score_batch(_canonical_brief(), [], {"gemini": "fake"})
        self.assertEqual(outcome.scores, [])
        self.assertEqual(outcome.llm_scored, 0)
        self.assertEqual(outcome.heuristic_scored, 0)


class AddScoredTargetsTests(unittest.TestCase):
    """Test 8: atomic persistence, tenant isolation, and the length guard."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = mock.patch.object(db, "DB_PATH", Path(self._tmpdir.name) / "outpost.db")
        self._db_patch.start()
        db.init()

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()

    @staticmethod
    def _candidate(name: str) -> Candidate:
        return Candidate(
            source="seed", external_id=None, name=name,
            handle_or_domain=f"{name.lower()}.com", reach=10, location="US",
            raw={"name": name},
        )

    @staticmethod
    def _score(fit_score: int) -> TargetScore:
        return TargetScore(
            fit_score=fit_score,
            reasons=[FitReason(reason="r", evidence_key="employees", evidence_value="10")],
            scored_by="heuristic",
        )

    def test_writes_targets_and_scores_together_scoped_to_workspace(self):
        ws_a = db.create_workspace("Alpha")
        ws_b = db.create_workspace("Beta")
        brief_json = _canonical_brief().model_dump_json()
        camp_a = db.create_campaign(ws_a, "promo", brief_json, "business")
        camp_b = db.create_campaign(ws_b, "promo", brief_json, "business")

        candidates = [self._candidate("C1"), self._candidate("C2")]
        scores = [self._score(90), self._score(20)]
        db.add_scored_targets(ws_a, camp_a, candidates, "seed", scores)

        targets_a = db.list_targets(ws_a, camp_a)
        self.assertEqual(len(targets_a), 2)
        self.assertEqual({t["fit_score"] for t in targets_a}, {90, 20})
        for t in targets_a:
            self.assertTrue(json.loads(t["fit_reasons_json"]))

        # Workspace B sees none of A's rows.
        self.assertEqual(db.list_targets(ws_b, camp_b), [])

    def test_length_mismatch_raises_and_writes_zero_rows(self):
        ws = db.create_workspace("Solo")
        camp = db.create_campaign(ws, "promo", _canonical_brief().model_dump_json(), "business")
        candidates = [self._candidate("C1"), self._candidate("C2")]
        scores = [self._score(90)]  # one short

        with self.assertRaises(ValueError):
            db.add_scored_targets(ws, camp, candidates, "seed", scores)

        self.assertEqual(db.list_targets(ws, camp), [])


class ZeroTargetCampaignTests(unittest.TestCase):
    """Test 9: a campaign with no discovered targets skips scoring cleanly."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = mock.patch.object(db, "DB_PATH", Path(self._tmpdir.name) / "outpost.db")
        self._db_patch.start()
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("GEMINI_API_KEY", None)
        db.init()

        from fastapi.testclient import TestClient

        from app.main import app

        self._client_ctx = TestClient(app)
        self.client = self._client_ctx.__enter__()
        self.workspace_id = db.create_workspace("Test WS")
        self.client.cookies.set("workspace_id", str(self.workspace_id))

    def tearDown(self):
        self._client_ctx.__exit__(None, None, None)
        self._env_patch.stop()
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def test_zero_discovered_targets_skips_scoring_and_writes_no_targets(self):
        empty_result = SourceResult([], SourceStatus.SEED_ERROR, "apollo", "seed", "seed data could not be loaded")
        with mock.patch("app.main.sources.discover", return_value=empty_result):
            resp = self.client.post(
                "/campaigns",
                data={"promoting_what": "US distributors for magnesium", "target_type": "business"},
                follow_redirects=False,
            )
        self.assertEqual(resp.status_code, 303)
        campaign_id = int(resp.headers["location"].rsplit("/", 1)[1])
        self.assertEqual(db.list_targets(self.workspace_id, campaign_id), [])
        actions = {row["action"] for row in db.list_audit(self.workspace_id, campaign_id)}
        self.assertIn("scoring.skipped_no_targets", actions)


# --- Hardening pass: post-Slice-3 findings --------------------------------


class FakeGeminiResponse:
    """A minimal httpx.Response stand-in, enough to drive a rejected-key path."""

    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "https://example.test"),
                response=self,
            )


class KnownInvalidKeyTests(unittest.TestCase):
    """Finding 1: a Gemini key already rejected during intake must not be
    asked again during scoring — that's a second live call for an answer
    intake already has."""

    def test_known_invalid_key_reason_skips_the_llm_call_entirely(self):
        with mock.patch("app.llm.generate_structured") as mocked:
            outcome = scoring.score_batch(
                _canonical_brief(),
                _two_target_evidence(),
                {"gemini": "fake"},
                known_invalid_key_reason="credential rejected during intake",
            )
        mocked.assert_not_called()
        self.assertEqual(outcome.status, ScoreStatus.INVALID_GEMINI_KEY)
        self.assertEqual(outcome.llm_scored, 0)
        self.assertEqual(outcome.heuristic_scored, 2)
        self.assertEqual(outcome.reason, "credential rejected during intake")

    def test_omitted_known_invalid_key_reason_calls_the_llm_as_normal(self):
        # No regression: without the flag, score_batch behaves exactly as
        # before (still calls the LLM once for a normal request).
        with mock.patch("app.llm.generate_structured", return_value=None) as mocked:
            outcome = scoring.score_batch(_canonical_brief(), _two_target_evidence(), {})
        mocked.assert_called_once()
        self.assertEqual(outcome.status, ScoreStatus.NO_GEMINI_KEY)


class KnownInvalidKeyRouteTests(unittest.TestCase):
    """Finding 1, at the route level: one campaign request with a rejected
    Gemini key must make exactly one live Gemini HTTP call total (intake's),
    not two (intake's plus a redundant one from scoring)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = mock.patch.object(db, "DB_PATH", Path(self._tmpdir.name) / "outpost.db")
        self._db_patch.start()
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("GEMINI_API_KEY", None)
        db.init()

        from fastapi.testclient import TestClient

        from app.main import app

        self._client_ctx = TestClient(app)
        self.client = self._client_ctx.__enter__()
        self.workspace_id = db.create_workspace("Test WS")
        self.client.cookies.set("workspace_id", str(self.workspace_id))
        db.save_setting(self.workspace_id, "gemini", "fake-invalid-gemini-key")

    def tearDown(self):
        self._client_ctx.__exit__(None, None, None)
        self._env_patch.stop()
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def test_one_campaign_request_makes_exactly_one_gemini_call(self):
        rejected = FakeGeminiResponse(403, {"error": {"message": "credential rejected"}})
        with mock.patch("app.llm.httpx.post", return_value=rejected) as post:
            resp = self.client.post(
                "/campaigns",
                data={"promoting_what": "US distributors for magnesium", "target_type": "business"},
                follow_redirects=False,
            )
        self.assertEqual(resp.status_code, 303)
        # Exactly one live call for the whole request — intake's — not a
        # second one from scoring re-asking a credential already known bad.
        self.assertEqual(post.call_count, 1)

        campaign_id = int(resp.headers["location"].rsplit("/", 1)[1])
        actions = {row["action"] for row in db.list_audit(self.workspace_id, campaign_id)}
        self.assertIn("intake.invalid_gemini_key", actions)
        self.assertIn("scoring.invalid_gemini_key", actions)
        targets = db.list_targets(self.workspace_id, campaign_id)
        self.assertTrue(targets)
        self.assertTrue(all(t["fit_score"] is not None for t in targets))


class ApolloEmptyOrgGroundingTests(unittest.TestCase):
    """Finding 2: an Apollo organization with no fields at all must not
    produce a fabricated, ungrounded fallback citation."""

    def test_empty_org_normalizes_to_a_non_blank_name(self):
        # Mirrors ApolloSource._to_candidate's own "Unknown company" default
        # for Candidate.name — evidence["name"] must never diverge from it.
        normalized = apollo_normalize_evidence({})
        self.assertEqual(normalized["name"], "Unknown company")

    def test_heuristic_on_empty_org_evidence_is_grounded(self):
        evidence = apollo_normalize_evidence({})  # every field but name is None
        brief = _canonical_brief()
        score, reasons = _heuristic(brief, evidence)
        self.assertEqual(len(reasons), 1)
        self.assertTrue(_is_grounded(reasons[0], evidence))
        self.assertEqual(reasons[0].evidence_key, "name")
        self.assertEqual(reasons[0].evidence_value, "Unknown company")

    def test_fully_blank_evidence_yields_zero_reasons_not_a_fabricated_one(self):
        # A hypothetical source row with nothing usable at all, not even a
        # name: honestly reporting "no reasons" beats inventing a citation
        # that doesn't match the evidence.
        evidence = {"name": None, "industry": None, "employees": None, "country": None, "domain": None}
        score, reasons = _heuristic(_canonical_brief(), evidence)
        self.assertEqual(score, 0)
        self.assertEqual(reasons, [])


class StemmingTests(unittest.TestCase):
    """Finding 3: exact token matching misses "distributors" vs "distribution";
    the explanation text must only describe what was actually evaluated."""

    def test_distribution_family_words_share_one_stem(self):
        stems = {_stem("distribution"), _stem("distributors"), _stem("distributor"), _stem("distribute")}
        self.assertEqual(len(stems), 1)

    def test_natural_distributors_niche_matches_a_distribution_industry(self):
        # The exact demo phrasing that previously scored zero industry
        # overlap purely because of the -tion vs -ors suffix mismatch.
        brief = Brief(
            product="magnesium supplements",
            audience="distributors",
            tone="Professional",
            target_type="business",
            niche_or_industry="US distributors for magnesium",
            target_countries=["United States"],
        )
        evidence = {
            "name": "Northbridge Distribution Co.",
            "industry": "Wholesale distribution",
            "employees": 180,
            "country": "United States",
            "domain": "northbridgedist.com",
        }
        score, reasons = _heuristic(brief, evidence)
        industry_reason = next(r for r in reasons if r.evidence_key == "industry")
        self.assertIn("overlaps", industry_reason.reason)
        self.assertTrue(_is_grounded(industry_reason, evidence))

    def test_no_overlap_reason_does_not_mention_product(self):
        # The heuristic never reads brief.product for this component — the
        # explanation must not claim it does.
        brief = _canonical_brief()
        evidence = {
            "name": "Lakeside Software Studio", "industry": "Consumer mobile apps",
            "employees": 12, "country": "United States", "domain": "lakesidesoftware.io",
        }
        _, reasons = _heuristic(brief, evidence)
        industry_reason = next(r for r in reasons if r.evidence_key == "industry")
        self.assertNotIn("product", industry_reason.reason)
        self.assertIn("niche", industry_reason.reason)

    def test_anchor_scores_are_unchanged_by_stemming(self):
        # The canonical brief's niche text already matches these industries
        # verbatim, so stemming must not change the previously-verified
        # anchor table (regression guard for the stemming change itself).
        brief = _canonical_brief()
        for evidence, expected in [
            (CORNERSTONE, 90), (MERIDIAN, 90), (NORTHBRIDGE, 60),
            (CASCADE, 40), (IRONCLAD, 40), (SUMMIT, 40), (LAKESIDE, 20),
        ]:
            score, _ = _heuristic(brief, evidence)
            self.assertEqual(score, expected, evidence["name"])


class EmployeesCoercionTests(unittest.TestCase):
    """Finding 4: a non-int employees value must never raise, in
    normalize_evidence or in the heuristic's own arithmetic."""

    def test_coerce_int_handles_common_shapes(self):
        self.assertEqual(coerce_int(180), 180)
        self.assertEqual(coerce_int(180.0), 180)
        self.assertEqual(coerce_int("180"), 180)
        self.assertEqual(coerce_int(" 180 "), 180)
        self.assertIsNone(coerce_int("not a number"))
        self.assertIsNone(coerce_int(None))
        self.assertIsNone(coerce_int(True))
        self.assertIsNone(coerce_int(False))

    def test_apollo_normalize_evidence_coerces_a_string_employee_count(self):
        raw = {"name": "Acme", "estimated_num_employees": "180"}
        self.assertEqual(apollo_normalize_evidence(raw)["employees"], 180)

    def test_apollo_normalize_evidence_drops_an_unparseable_employee_count(self):
        raw = {"name": "Acme", "estimated_num_employees": "a lot"}
        self.assertIsNone(apollo_normalize_evidence(raw)["employees"])

    def test_heuristic_treats_a_string_employees_value_as_unavailable_not_a_crash(self):
        # Bypasses normalize_evidence entirely, proving _heuristic's own
        # defensive guard — not just the upstream fix — holds independently.
        evidence = {
            "name": "Acme", "industry": "Wholesale distribution",
            "employees": "180", "country": "United States", "domain": "acme.com",
        }
        score, reasons = _heuristic(_canonical_brief(), evidence)  # must not raise
        self.assertFalse(any(r.evidence_key == "employees" for r in reasons))

    def test_heuristic_treats_a_bool_employees_value_as_unavailable(self):
        evidence = {
            "name": "Acme", "industry": "Wholesale distribution",
            "employees": True, "country": "United States", "domain": "acme.com",
        }
        score, reasons = _heuristic(_canonical_brief(), evidence)  # must not raise
        self.assertFalse(any(r.evidence_key == "employees" for r in reasons))


if __name__ == "__main__":
    unittest.main(verbosity=2)
