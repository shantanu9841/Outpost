"""Maintained regression tests for Slice 5 (creator sources and demo mode).

Retained unittest tests (not disposable scripts), per collaboration.md rule
9/11 and SLICE_5_PLAN.md §7.1. Every provider call is mocked at the httpx
boundary — no live call, no real key, no outpost.db writes outside a
temporary SQLite file. Covers every acceptance criterion in §7.1 (1-16).

Run: python -m unittest tests.test_slice5_creators -v
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from app import audit_banners, db, sources
from app.agent.scoring import ScoreStatus, _heuristic, _heuristic_creator, _is_grounded
from app.models import Brief, Candidate
from app.sources import apify as apify_module
from app.sources import youtube as youtube_module
from app.sources.apify import ApifySource
from app.sources.base import SourceStatus
from app.sources.seed import SEEDS_DIR, SeedSource
from app.sources.youtube import YouTubeSource

FAKE_APIFY_KEY = "fake-apify-key-not-a-real-credential"
FAKE_YOUTUBE_KEY = "fake-youtube-key-not-a-real-credential"

_UNSET = object()


def _creator_brief(target_countries=None, niche="wellness fitness mindfulness") -> Brief:
    return Brief(
        product="wellness gear",
        audience="fitness-minded creators",
        tone="Friendly",
        target_type="creator",
        niche_or_industry=niche,
        target_countries=target_countries or ["United States"],
    )


def _business_brief() -> Brief:
    return Brief(
        product="magnesium supplements",
        audience="distributors",
        tone="Professional",
        target_type="business",
        niche_or_industry="health & wellness distribution",
        target_countries=["United States"],
    )


class FakeResponse:
    """A minimal stand-in for httpx.Response (mirrors test_slice2_hardening's)."""

    def __init__(self, status_code, json_data=_UNSET, json_error=False):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error or self._json_data is _UNSET:
            raise json.JSONDecodeError("Expecting value", "", 0)
        return self._json_data


def _run_response(run_id="run1", status="SUCCEEDED", dataset_id="ds1"):
    return FakeResponse(200, {"data": {"id": run_id, "status": status, "defaultDatasetId": dataset_id}})


def _dataset_response(items):
    return FakeResponse(200, items)


def _counting_now():
    state = {"t": 0.0}

    def _now():
        state["t"] += 1.0
        return state["t"]

    return _now


# --- 1-4: ApifySource merge, partial, dual-failure, precedence --------------


class ApifyMergeTests(unittest.TestCase):
    def _search(self, post_side_effect, get_side_effect, brief=None):
        with mock.patch("app.sources.apify.httpx.post", side_effect=post_side_effect), \
             mock.patch("app.sources.apify.httpx.get", side_effect=get_side_effect):
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            return source.search(brief or _creator_brief())

    def test_full_success_merges_both_platforms(self):
        ig_items = [
            {"fullName": "Aria", "username": "aria", "followersCount": 50000, "biography": "wellness"}
        ]
        tt_items = [
            {"nickname": "Sam", "uniqueId": "sam", "fans": 30000, "signature": "fitness"}
        ]
        result = self._search(
            [_run_response("r-ig"), _run_response("r-tt")],
            [_dataset_response(ig_items), _dataset_response(tt_items)],
        )
        self.assertEqual(result.status, SourceStatus.OK)
        self.assertEqual(result.source_used, "apify")
        self.assertEqual(result.source_attempted, "apify")
        self.assertIsNone(result.reason)
        self.assertEqual(len(result.candidates), 2)
        platforms = {c.raw["_outpost_platform"] for c in result.candidates}
        self.assertEqual(platforms, {"instagram", "tiktok"})

    def test_partial_success_when_one_platform_fails(self):
        ig_items = [{"fullName": "Aria", "username": "aria", "followersCount": 50000}]
        result = self._search(
            [_run_response("r-ig"), FakeResponse(500, {"error": {"message": "server error"}})],
            [_dataset_response(ig_items)],
        )
        self.assertEqual(result.status, SourceStatus.PARTIAL_RESULTS)
        self.assertEqual(result.source_used, "apify")
        self.assertEqual(len(result.candidates), 1)
        self.assertIn("TikTok", result.reason)
        self.assertIn("Instagram", result.reason)

    def test_dual_failure_falls_back_to_creator_seed_via_discover(self):
        with mock.patch(
            "app.sources.apify.httpx.post",
            side_effect=[
                FakeResponse(500, {"error": {"message": "boom ig"}}),
                FakeResponse(500, {"error": {"message": "boom tt"}}),
            ],
        ):
            result = sources.discover(_creator_brief(), settings={"apify": FAKE_APIFY_KEY})
        self.assertEqual(result.status, SourceStatus.PROVIDER_ERROR)
        self.assertEqual(result.source_attempted, "apify")
        self.assertEqual(result.source_used, "seed")
        self.assertGreater(len(result.candidates), 0)
        self.assertIn("instagram:", result.reason)
        self.assertIn("tiktok:", result.reason)

    def test_status_precedence_when_dual_failures_differ(self):
        # Instagram 401 (INVALID_KEY) beats TikTok 429 (RATE_LIMITED).
        result = self._search(
            [FakeResponse(401, {"error": {"message": "bad token"}}), FakeResponse(429, {"error": {"message": "slow down"}})],
            [],
        )
        self.assertEqual(result.status, SourceStatus.INVALID_KEY)
        self.assertIn("instagram:", result.reason)
        self.assertIn("tiktok:", result.reason)

        # Reversed order: TikTok now has the higher-precedence status.
        result2 = self._search(
            [FakeResponse(429, {"error": {"message": "slow down"}}), FakeResponse(401, {"error": {"message": "bad token"}})],
            [],
        )
        self.assertEqual(result2.status, SourceStatus.INVALID_KEY)


# --- 5: routing priority ------------------------------------------------


class RoutingPriorityTests(unittest.TestCase):
    def test_youtube_used_when_only_youtube_key_present(self):
        search_resp = FakeResponse(200, {"items": [{"id": {"channelId": "c1"}}]})
        channels_resp = FakeResponse(
            200,
            {
                "items": [
                    {
                        "id": "c1",
                        "snippet": {"title": "Aria", "description": "wellness", "country": "US"},
                        "statistics": {"subscriberCount": "50000"},
                    }
                ]
            },
        )
        with mock.patch("app.sources.youtube.httpx.get", side_effect=[search_resp, channels_resp]):
            result = sources.discover(_creator_brief(), settings={"youtube": FAKE_YOUTUBE_KEY})
        self.assertEqual(result.status, SourceStatus.OK)
        self.assertEqual(result.source_used, "youtube")

    def test_apify_takes_priority_over_youtube_when_both_configured(self):
        # httpx.get is one shared module attribute across every source file
        # (apify.py and youtube.py both `import httpx` and call
        # httpx.get/httpx.post directly) — patching it via either dotted
        # path patches the same underlying object, so "assert youtube's
        # mock was never called" isn't meaningful here. Instead, prove
        # YouTube's endpoint was never hit by checking every recorded GET
        # call's URL went to Apify, not googleapis.com.
        with mock.patch("app.sources.apify.httpx.post", return_value=_run_response()), \
             mock.patch("app.sources.apify.httpx.get", return_value=_dataset_response([])) as get_mock:
            result = sources.discover(
                _creator_brief(), settings={"apify": FAKE_APIFY_KEY, "youtube": FAKE_YOUTUBE_KEY}
            )
        self.assertEqual(result.source_attempted, "apify")
        for call in get_mock.call_args_list:
            self.assertIn("api.apify.com", call.args[0])


# --- 6: seed fallback / zero-key routing --------------------------------


class _TempDbTestCase(unittest.TestCase):
    """Base: an isolated temp DB and a guaranteed-absent GEMINI_API_KEY."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = mock.patch.object(db, "DB_PATH", Path(self._tmpdir.name) / "outpost.db")
        self._db_patch.start()
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("GEMINI_API_KEY", None)
        db.init()

    def tearDown(self):
        self._env_patch.stop()
        self._db_patch.stop()
        self._tmpdir.cleanup()


class ZeroKeyCreatorCampaignTests(_TempDbTestCase):
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

    def test_no_creator_key_routes_to_seed_with_info_banner(self):
        all_creators = json.loads((SEEDS_DIR / "creators.json").read_text(encoding="utf-8"))

        resp = self.client.post(
            "/campaigns",
            data={"promoting_what": "wellness fitness mindfulness creators", "target_type": "creator"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        campaign_id = int(resp.headers["location"].rsplit("/", 1)[1])

        targets = db.list_targets(self.workspace_id, campaign_id)
        self.assertEqual(len(targets), len(all_creators))
        self.assertTrue(all(t["source"] == "seed" for t in targets))
        self.assertTrue(all(t["fit_score"] is not None for t in targets))

        actions = {row["action"] for row in db.list_audit(self.workspace_id, campaign_id)}
        self.assertIn("discovery.no_creator_key", actions)
        entry = audit_banners.CREATOR_DISCOVERY_MAP[SourceStatus.NO_KEY]
        self.assertEqual(entry[1], "info")

    def test_zero_key_creator_campaign_completes_through_pipeline(self):
        """Test 14: creator campaign -> seed discovery -> creator scoring ->
        draft -> approve -> pipeline, entirely on zero keys."""
        resp = self.client.post(
            "/campaigns",
            data={"promoting_what": "wellness fitness mindfulness creators", "target_type": "creator"},
            follow_redirects=False,
        )
        campaign_id = int(resp.headers["location"].rsplit("/", 1)[1])
        targets = db.list_targets(self.workspace_id, campaign_id)
        self.assertTrue(len(targets) > 0)
        strongest = max(targets, key=lambda t: t["fit_score"])

        draft_resp = self.client.post(f"/targets/{strongest['id']}/draft", follow_redirects=False)
        self.assertEqual(draft_resp.status_code, 303)

        pending = db.list_pending_drafts(self.workspace_id)
        self.assertEqual(len(pending), 1)
        draft_id = pending[0]["id"]

        approve_resp = self.client.post(
            f"/drafts/{draft_id}/action",
            data={"action": "approve", "body": pending[0]["body"]},
            follow_redirects=False,
        )
        self.assertEqual(approve_resp.status_code, 303)

        stage_resp = self.client.post(
            f"/targets/{strongest['id']}/stage", data={"stage": "contacted"}, follow_redirects=False
        )
        self.assertEqual(stage_resp.status_code, 303)

        pipeline_targets = db.list_pipeline_targets(self.workspace_id)
        self.assertEqual(len(pipeline_targets), 1)
        self.assertEqual(pipeline_targets[0]["stage"], "contacted")


# --- 7: creator scoring produces a demonstrable ranking -----------------


class CreatorSeedScoringTests(unittest.TestCase):
    def test_seed_spread_ranks_strong_over_partial_over_geo_or_weak_over_irrelevant(self):
        brief = _creator_brief()
        result = SeedSource("creator").search(brief)
        self.assertEqual(result.status, SourceStatus.OK)

        by_name = {}
        for candidate in result.candidates:
            evidence = sources.evidence_for("seed", "creator", candidate)
            score, reasons = _heuristic_creator(brief, evidence)
            self.assertTrue(reasons)
            for reason in reasons:
                self.assertTrue(_is_grounded(reason, evidence), f"{candidate.name}: {reason}")
            by_name[candidate.name] = score

        strong = by_name["Aria Wellness"]
        partial = by_name["FitLife Sam"]
        geo_mismatch = by_name["Berlin Wellness Guide"]
        weak = by_name["New Journey Nina"]
        irrelevant = by_name["Turbo Car Reviews"]

        self.assertGreater(strong, partial)
        self.assertGreater(partial, geo_mismatch)
        self.assertGreater(partial, weak)
        self.assertGreater(geo_mismatch, irrelevant)
        self.assertGreater(weak, irrelevant)


# --- 8: follower boundary bands ------------------------------------------


class FollowerBoundaryTests(unittest.TestCase):
    def _score_followers_only(self, followers):
        brief = _creator_brief()
        evidence = {"name": "Test Creator", "niche": None, "followers": followers, "country": None}
        return _heuristic_creator(brief, evidence)

    def test_boundary_pairs(self):
        cases = [
            (999, 5), (1_000, 15),
            (9_999, 15), (10_000, 25),
            (500_000, 25), (500_001, 15),
            (2_000_000, 15), (2_000_001, 5),
        ]
        for followers, expected_points in cases:
            score, reasons = self._score_followers_only(followers)
            self.assertEqual(score, expected_points, f"followers={followers}")
            self.assertEqual(len(reasons), 1)
            self.assertEqual(reasons[0].evidence_key, "followers")

    def test_missing_followers_scores_zero_with_no_followers_reason(self):
        brief = _creator_brief()
        evidence = {"name": "Test Creator", "niche": None, "followers": None, "country": None}
        score, reasons = _heuristic_creator(brief, evidence)
        self.assertEqual(score, 0)
        self.assertFalse(any(r.evidence_key == "followers" for r in reasons))
        # Falls back to the name-only citation rather than an empty list.
        self.assertEqual(reasons[0].evidence_key, "name")

    def test_non_integer_followers_scores_zero_with_no_followers_reason(self):
        brief = _creator_brief()
        for bad in (True, 12.5, "not-a-number", float("nan")):
            evidence = {"name": "Test Creator", "niche": None, "followers": bad, "country": None}
            score, reasons = _heuristic_creator(brief, evidence)
            self.assertEqual(score, 0, f"followers={bad!r}")
            self.assertFalse(any(r.evidence_key == "followers" for r in reasons))

    def test_country_absent_creator_is_capped_at_practical_maximum_85(self):
        brief = _creator_brief()
        evidence = {
            "name": "Test Creator",
            "niche": "wellness fitness mindfulness content",
            "followers": 100_000,
            "country": None,
        }
        score, reasons = _heuristic_creator(brief, evidence)
        self.assertEqual(score, 85)
        self.assertFalse(any(r.evidence_key == "country" for r in reasons))


# --- 9: target-type-aware LLM prompt --------------------------------------


class PromptTargetTypeTests(unittest.TestCase):
    def test_creator_system_prompt_describes_creators_not_companies(self):
        from app.agent.scoring import _system_prompt

        creator_prompt = _system_prompt("creator")
        business_prompt = _system_prompt("business")
        self.assertIn("creator", creator_prompt.lower())
        self.assertNotIn("candidate company", creator_prompt.lower())
        self.assertIn("candidate company", business_prompt.lower())

    def test_build_prompt_carries_target_type_and_labels_rows(self):
        from app.agent.scoring import _build_prompt

        creator_evidence = [{"name": "Aria", "niche": "wellness", "followers": 50000, "country": None}]
        creator_prompt_text = _build_prompt(_creator_brief(), creator_evidence)
        self.assertIn("target_type: creator", creator_prompt_text)
        self.assertIn("creator target", creator_prompt_text)

        business_evidence = [{"name": "Acme", "industry": "Wholesale", "employees": 100, "country": "United States"}]
        business_prompt_text = _build_prompt(_business_brief(), business_evidence)
        self.assertIn("target_type: business", business_prompt_text)
        self.assertIn("company target", business_prompt_text)


# --- 10: business-score regression protection -----------------------------


class BusinessRegressionTests(unittest.TestCase):
    def test_business_anchor_score_is_unchanged(self):
        # Pinned against docs/plans/completed/SLICE_3_PLAN.md §4.3's own anchor table
        # (test_slice3_scoring.HeuristicAnchorTests), reached through the
        # same public _heuristic() dispatcher creator scoring now shares.
        brief = _business_brief()
        cornerstone = {
            "name": "Cornerstone Wellness Distributors",
            "industry": "Health & wellness distribution",
            "employees": 75,
            "country": "United States",
            "domain": "cornerstonewellness.com",
        }
        score, reasons = _heuristic(brief, cornerstone)
        self.assertEqual(score, 90)
        for reason in reasons:
            self.assertTrue(_is_grounded(reason, cornerstone))


# --- 11: audit action-key non-collision -----------------------------------


class AuditActionCollisionTests(unittest.TestCase):
    def test_business_and_creator_discovery_maps_share_no_action_key(self):
        business_actions = {entry[0] for entry in audit_banners.DISCOVERY_MAP.values()}
        creator_actions = {entry[0] for entry in audit_banners.CREATOR_DISCOVERY_MAP.values()}
        creator_actions |= set(audit_banners.CREATOR_DISCOVERY_OK_ACTIONS.values())
        self.assertEqual(business_actions & creator_actions, set())

    def test_every_creator_action_resolves_through_the_shared_maps(self):
        for action, severity, template in audit_banners.CREATOR_DISCOVERY_MAP.values():
            self.assertIn(action, audit_banners.ACTION_LABELS)
            if severity is not None:
                self.assertIn(action, audit_banners.BANNER_BY_ACTION)
        for action in audit_banners.CREATOR_DISCOVERY_OK_ACTIONS.values():
            self.assertIn(action, audit_banners.ACTION_LABELS)
            self.assertNotIn(action, audit_banners.BANNER_BY_ACTION)  # silent on success


# --- 12: tenant isolation ---------------------------------------------------


class TenantIsolationTests(_TempDbTestCase):
    def test_creator_targets_audit_and_drafts_are_scoped_per_workspace(self):
        ws_a = db.create_workspace("Alpha")
        ws_b = db.create_workspace("Beta")
        brief = _creator_brief()
        camp_a = db.create_campaign(ws_a, "a", brief.model_dump_json(), "creator")
        camp_b = db.create_campaign(ws_b, "b", brief.model_dump_json(), "creator")

        seed = SeedSource("creator").search(brief)
        scores = [_heuristic_creator(brief, sources.evidence_for("seed", "creator", c)) for c in seed.candidates]
        from app.agent.scoring import TargetScore

        target_scores = [TargetScore(score, reasons, "heuristic") for score, reasons in scores]
        db.add_scored_targets(ws_a, camp_a, seed.candidates, "seed", target_scores)
        db.add_audit(ws_a, camp_a, "agent", "discovery.no_creator_key")

        self.assertEqual(db.list_targets(ws_b, camp_b), [])
        self.assertEqual(db.list_audit(ws_b, camp_b), [])
        self.assertEqual(len(db.list_targets(ws_a, camp_a)), len(seed.candidates))
        self.assertEqual(db.list_targets(ws_b, camp_a), [])


# --- 13: sanitized audit details --------------------------------------------


class SanitizedReasonTests(unittest.TestCase):
    def test_apify_reason_redacts_an_echoed_key(self):
        response = FakeResponse(401, {"error": {"message": f"token {FAKE_APIFY_KEY} rejected"}})
        reason = apify_module._safe_reason(response, FAKE_APIFY_KEY)
        self.assertNotIn(FAKE_APIFY_KEY, reason)
        self.assertIn("[REDACTED]", reason)

    def test_youtube_reason_redacts_an_echoed_key(self):
        response = FakeResponse(
            400, {"error": {"message": f"key {FAKE_YOUTUBE_KEY} not valid", "status": "INVALID_ARGUMENT"}}
        )
        reason = youtube_module._safe_reason(response, FAKE_YOUTUBE_KEY)
        self.assertNotIn(FAKE_YOUTUBE_KEY, reason)
        self.assertIn("[REDACTED]", reason)

    def test_apify_dual_failure_reason_has_no_key_or_url(self):
        with mock.patch(
            "app.sources.apify.httpx.post",
            side_effect=[
                FakeResponse(401, {"error": {"message": f"token {FAKE_APIFY_KEY} rejected"}}),
                FakeResponse(401, {"error": {"message": f"token {FAKE_APIFY_KEY} rejected"}}),
            ],
        ):
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            result = source.search(_creator_brief())
        self.assertNotIn(FAKE_APIFY_KEY, result.reason)
        self.assertNotIn("api.apify.com", result.reason)


# --- 14: covered above by ZeroKeyCreatorCampaignTests ----------------------


# --- 15: transport authentication and bounds --------------------------------


class ApifyTransportTests(unittest.TestCase):
    def test_start_run_sends_bearer_header_and_run_bounding_params_never_token_query(self):
        with mock.patch("app.sources.apify.httpx.post", return_value=_run_response()) as post, \
             mock.patch("app.sources.apify.httpx.get", return_value=_dataset_response([])):
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            source._run_instagram(_creator_brief())

        self.assertEqual(post.call_count, 1)
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {FAKE_APIFY_KEY}")
        self.assertNotIn("token", kwargs["params"])
        self.assertEqual(kwargs["params"]["timeout"], apify_module.RUN_TIMEOUT_SECS)
        self.assertEqual(kwargs["params"]["maxItems"], apify_module.MAX_ITEMS)
        self.assertEqual(kwargs["params"]["maxTotalChargeUsd"], apify_module.MAX_TOTAL_CHARGE_USD)
        self.assertEqual(kwargs["timeout"], apify_module.REQUEST_TIMEOUT_SECS)

    def test_poll_and_fetch_send_bearer_header_never_token_query(self):
        poll_resp = _run_response(status="RUNNING")
        poll_done = _run_response(status="SUCCEEDED")
        with mock.patch("app.sources.apify.httpx.post", return_value=_run_response(status="RUNNING")), \
             mock.patch(
                 "app.sources.apify.httpx.get", side_effect=[poll_resp, poll_done, _dataset_response([])]
             ) as get:
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            candidates, status, reason = source._run_instagram(_creator_brief())

        self.assertEqual(status, SourceStatus.OK)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Authorization"], f"Bearer {FAKE_APIFY_KEY}")
            self.assertNotIn("token", call.kwargs.get("params", {}))
            self.assertEqual(call.kwargs["timeout"], apify_module.REQUEST_TIMEOUT_SECS)

    def test_poll_budget_exhaustion_maps_to_provider_error_without_raising(self):
        calls = {"n": 0}

        def fake_now():
            calls["n"] += 1
            return 0 if calls["n"] == 1 else apify_module.POLL_BUDGET_SECS + 1

        with mock.patch(
            "app.sources.apify.httpx.post",
            return_value=_run_response(status="RUNNING"),
        ), mock.patch("app.sources.apify.httpx.get") as get_mock:
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=fake_now)
            candidates, status, reason = source._run_instagram(_creator_brief())

        self.assertEqual(candidates, [])
        self.assertEqual(status, SourceStatus.PROVIDER_ERROR)
        self.assertIn("budget", reason)
        get_mock.assert_not_called()

    def test_poll_budget_is_rechecked_after_the_final_partial_sleep(self):
        state = {"calls": 0, "time": 0.0}
        sleeps = []

        def fake_now():
            state["calls"] += 1
            if state["calls"] == 2:
                state["time"] = apify_module.POLL_BUDGET_SECS - 1
            return state["time"]

        def fake_sleep(seconds):
            sleeps.append(seconds)
            state["time"] += seconds

        with mock.patch(
            "app.sources.apify.httpx.post",
            return_value=_run_response(status="RUNNING"),
        ), mock.patch("app.sources.apify.httpx.get") as get_mock:
            source = ApifySource(FAKE_APIFY_KEY, sleep=fake_sleep, now=fake_now)
            candidates, status, reason = source._run_instagram(_creator_brief())

        self.assertEqual(candidates, [])
        self.assertEqual(status, SourceStatus.PROVIDER_ERROR)
        self.assertIn("budget", reason)
        self.assertEqual(sleeps, [1])
        get_mock.assert_not_called()

    def test_poll_request_timeout_is_capped_to_the_remaining_budget(self):
        state = {"calls": 0, "time": 0.0}

        def fake_now():
            state["calls"] += 1
            if state["calls"] == 2:
                state["time"] = 125.0
            return state["time"]

        def fake_sleep(seconds):
            state["time"] += seconds

        with mock.patch(
            "app.sources.apify.httpx.post",
            return_value=_run_response(status="RUNNING"),
        ), mock.patch(
            "app.sources.apify.httpx.get",
            side_effect=[_run_response(status="SUCCEEDED"), _dataset_response([])],
        ) as get_mock:
            source = ApifySource(FAKE_APIFY_KEY, sleep=fake_sleep, now=fake_now)
            candidates, status, reason = source._run_instagram(_creator_brief())

        self.assertEqual(status, SourceStatus.OK)
        self.assertEqual(candidates, [])
        self.assertIsNone(reason)
        self.assertEqual(get_mock.call_args_list[0].kwargs["timeout"], 22.0)
        self.assertEqual(get_mock.call_args_list[1].kwargs["timeout"], apify_module.REQUEST_TIMEOUT_SECS)

    def test_poll_response_arriving_after_deadline_is_rejected(self):
        state = {"calls": 0, "time": 0.0}

        def fake_now():
            state["calls"] += 1
            if state["calls"] == 2:
                state["time"] = 100.0
            return state["time"]

        def fake_sleep(seconds):
            state["time"] += seconds

        def finish_after_deadline(*args, **kwargs):
            state["time"] = apify_module.POLL_BUDGET_SECS + 1
            return _run_response(status="SUCCEEDED")

        with mock.patch(
            "app.sources.apify.httpx.post",
            return_value=_run_response(status="RUNNING"),
        ), mock.patch("app.sources.apify.httpx.get", side_effect=finish_after_deadline) as get_mock:
            source = ApifySource(FAKE_APIFY_KEY, sleep=fake_sleep, now=fake_now)
            candidates, status, reason = source._run_instagram(_creator_brief())

        self.assertEqual(candidates, [])
        self.assertEqual(status, SourceStatus.PROVIDER_ERROR)
        self.assertIn("budget", reason)
        self.assertEqual(get_mock.call_count, 1)

    def test_transport_error_at_each_stage_maps_to_network_error(self):
        with mock.patch("app.sources.apify.httpx.post", side_effect=httpx.ConnectTimeout("x")):
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            _, status, _ = source._run_instagram(_creator_brief())
        self.assertEqual(status, SourceStatus.NETWORK_ERROR)

        with mock.patch("app.sources.apify.httpx.post", return_value=_run_response(status="RUNNING")), \
             mock.patch("app.sources.apify.httpx.get", side_effect=httpx.ConnectTimeout("x")):
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            _, status, _ = source._run_instagram(_creator_brief())
        self.assertEqual(status, SourceStatus.NETWORK_ERROR)

    def test_terminal_failure_statuses_map_to_provider_error(self):
        for terminal_status in ("FAILED", "ABORTED", "TIMED-OUT"):
            with mock.patch(
                "app.sources.apify.httpx.post", return_value=_run_response(status=terminal_status)
            ):
                source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
                candidates, status, reason = source._run_instagram(_creator_brief())
            self.assertEqual(candidates, [])
            self.assertEqual(status, SourceStatus.PROVIDER_ERROR, terminal_status)

    def test_non_array_dataset_items_is_provider_error_without_raising(self):
        with mock.patch("app.sources.apify.httpx.post", return_value=_run_response()), \
             mock.patch("app.sources.apify.httpx.get", return_value=FakeResponse(200, {"not": "a list"})):
            source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
            candidates, status, reason = source._run_instagram(_creator_brief())
        self.assertEqual(candidates, [])
        self.assertEqual(status, SourceStatus.PROVIDER_ERROR)

    def test_start_run_status_mapping(self):
        cases = [
            (401, SourceStatus.INVALID_KEY),
            (402, SourceStatus.INSUFFICIENT_PLAN),
            (403, SourceStatus.INSUFFICIENT_PLAN),
            (429, SourceStatus.RATE_LIMITED),
            (500, SourceStatus.PROVIDER_ERROR),
        ]
        for code, expected in cases:
            with mock.patch(
                "app.sources.apify.httpx.post", return_value=FakeResponse(code, {"error": {"message": "x"}})
            ):
                source = ApifySource(FAKE_APIFY_KEY, sleep=lambda s: None, now=_counting_now())
                _, status, _ = source._run_instagram(_creator_brief())
            self.assertEqual(status, expected, code)


class YouTubeTransportTests(unittest.TestCase):
    def _search(self, side_effect):
        with mock.patch("app.sources.youtube.httpx.get", side_effect=side_effect) as get:
            source = YouTubeSource(FAKE_YOUTUBE_KEY)
            result = source.search(_creator_brief())
            return result, get

    def test_search_and_channels_send_header_key_never_query_param(self):
        search_resp = FakeResponse(200, {"items": [{"id": {"channelId": "c1"}}]})
        channels_resp = FakeResponse(
            200,
            {
                "items": [
                    {
                        "id": "c1",
                        "snippet": {"title": "Aria", "description": "wellness", "country": "US"},
                        "statistics": {"subscriberCount": "50000"},
                    }
                ]
            },
        )
        result, get = self._search([search_resp, channels_resp])
        self.assertEqual(result.status, SourceStatus.OK)
        self.assertEqual(get.call_count, 2)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["headers"]["X-goog-api-key"], FAKE_YOUTUBE_KEY)
            self.assertNotIn("key", call.kwargs["params"])
            self.assertEqual(call.kwargs["timeout"], youtube_module.REQUEST_TIMEOUT_SECS)

    def test_status_mapping(self):
        cases = [
            (FakeResponse(400, {"error": {"message": "API key not valid. Please pass a valid API key."}}), SourceStatus.INVALID_KEY),
            (FakeResponse(403, {"error": {"errors": [{"reason": "keyInvalid"}], "message": "bad"}}), SourceStatus.INVALID_KEY),
            (FakeResponse(403, {"error": {"errors": [{"reason": "quotaExceeded"}], "message": "over"}}), SourceStatus.RATE_LIMITED),
            (FakeResponse(403, {"error": {"errors": [{"reason": "rateLimitExceeded"}], "message": "slow"}}), SourceStatus.RATE_LIMITED),
            (FakeResponse(500, {"error": {"message": "server error"}}), SourceStatus.PROVIDER_ERROR),
        ]
        for response, expected in cases:
            result, _ = self._search([response])
            self.assertEqual(result.status, expected)

    def test_network_error_is_network_error(self):
        with mock.patch("app.sources.youtube.httpx.get", side_effect=httpx.ConnectTimeout("x")):
            result = YouTubeSource(FAKE_YOUTUBE_KEY).search(_creator_brief())
        self.assertEqual(result.status, SourceStatus.NETWORK_ERROR)

    def test_no_search_results_is_ok_with_no_candidates_and_no_channels_call(self):
        with mock.patch(
            "app.sources.youtube.httpx.get", return_value=FakeResponse(200, {"items": []})
        ) as get:
            result = YouTubeSource(FAKE_YOUTUBE_KEY).search(_creator_brief())
        self.assertEqual(result.status, SourceStatus.OK)
        self.assertEqual(result.candidates, [])
        self.assertEqual(get.call_count, 1)  # channels.list never called

    def test_malformed_search_payload_is_provider_error_not_empty_success(self):
        malformed_responses = [
            FakeResponse(200, json_error=True),
            FakeResponse(200, []),
            FakeResponse(200, {}),
            FakeResponse(200, {"items": {}}),
            FakeResponse(200, {"items": [None]}),
            FakeResponse(200, {"items": [{}]}),
            FakeResponse(200, {"items": [{"id": {}}]}),
            FakeResponse(200, {"items": [{"id": {"channelId": "  "}}]}),
        ]

        for response in malformed_responses:
            with self.subTest(payload=response._json_data):
                result, get = self._search([response])
                self.assertEqual(result.status, SourceStatus.PROVIDER_ERROR)
                self.assertEqual(result.candidates, [])
                self.assertIn("unexpected search payload", result.reason)
                self.assertEqual(get.call_count, 1)


# --- 16: platform provenance and rendering ----------------------------------


class PlatformProvenanceTests(_TempDbTestCase):
    def test_merged_apify_candidates_retain_distinct_platform_through_persistence(self):
        ig_candidate = ApifySource._instagram_to_candidate(
            {"fullName": "Aria", "username": "aria", "followersCount": 50000, "biography": "wellness"}
        )
        tt_candidate = ApifySource._tiktok_to_candidate(
            {"nickname": "Sam", "uniqueId": "sam", "fans": 30000, "signature": "fitness"}
        )
        self.assertEqual(ig_candidate.raw["_outpost_platform"], "instagram")
        self.assertEqual(tt_candidate.raw["_outpost_platform"], "tiktok")
        self.assertEqual(ig_candidate.source, "apify")
        self.assertEqual(tt_candidate.source, "apify")

        ws = db.create_workspace("WS")
        camp = db.create_campaign(ws, "p", _creator_brief().model_dump_json(), "creator")
        from app.agent.scoring import TargetScore
        from app.models import FitReason

        dummy_score = TargetScore(
            50, [FitReason(reason="ok", evidence_key="name", evidence_value="Aria")], "heuristic"
        )
        db.add_scored_targets(ws, camp, [ig_candidate, tt_candidate], "apify", [dummy_score, dummy_score])

        rows = db.list_targets(ws, camp)
        self.assertTrue(all(r["source"] == "apify" for r in rows))
        platforms = {json.loads(r["raw_json"])["_outpost_platform"] for r in rows}
        self.assertEqual(platforms, {"instagram", "tiktok"})


    def test_documented_tiktok_author_meta_shape_normalizes_creator_fields(self):
        candidate = ApifySource._tiktok_to_candidate(
            {
                "authorMeta": {
                    "id": "6784642169778881542",
                    "name": "exampleuser",
                    "nickName": "Example User",
                    "signature": "Wellness and fitness creator",
                    "fans": 12500,
                    "region": "US",
                }
            }
        )

        self.assertEqual(candidate.name, "Example User")
        self.assertEqual(candidate.handle_or_domain, "exampleuser")
        self.assertEqual(candidate.external_id, "6784642169778881542")
        self.assertEqual(candidate.reach, 12500)
        self.assertEqual(candidate.location, "US")
        self.assertEqual(
            sources.evidence_for("apify", "creator", candidate),
            {
                "name": "Example User",
                "niche": "Wellness and fitness creator",
                "followers": 12500,
                "country": "US",
                "handle": "exampleuser",
                "platform": "tiktok",
            },
        )
        self.assertNotEqual(candidate.name, "Unknown company")

    def test_tiktok_rows_without_creator_metadata_are_rejected(self):
        for malformed in ({}, {"authorMeta": []}, {"authorMeta": {}}):
            with self.subTest(payload=malformed):
                with self.assertRaises(ValueError):
                    ApifySource._tiktok_to_candidate(malformed)
    def test_campaign_detail_renders_platform_for_every_creator_seed_row(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            ws = db.create_workspace("WS")
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(
                "/campaigns",
                data={"promoting_what": "wellness fitness mindfulness creators", "target_type": "creator"},
                follow_redirects=True,
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.text
            self.assertIn("YouTube", body)
            self.assertIn("Instagram", body)
            self.assertIn("TikTok", body)
            self.assertIn("Followers", body)
            self.assertIn("Handle", body)
            self.assertIn("Platform", body)
            self.assertNotIn("Company", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
