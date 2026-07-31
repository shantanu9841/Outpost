"""Maintained regression tests for Slice 4 (drafting, approval queue, pipeline).

Retained unittest tests (SLICE_4_PLAN.md §11.1), not disposable scripts. Every
Gemini call is mocked at app.agent.drafting.llm.generate_structured — no real
provider call, no real key, no outpost.db writes (a temporary SQLite file is
used wherever a DB is touched). Items 20-21 are the deliberate exception to
"mocked": they exercise two real, separate sqlite3 connections against the
same on-disk temp file to prove SQLite's writer serialization actually closes
the concurrency gaps SLICE_4_PLAN.md §5.1 describes.

Run: python -m unittest tests.test_slice4_drafting -v
"""

import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from app import db, llm
from app.agent import drafting
from app.agent.drafting import DraftResult, DraftStatus
from app.models import Brief, OutreachDraft, validate_draft_body
from app.sources.base import DEFAULT_NAME


def _brief() -> Brief:
    return Brief(
        product="magnesium supplements",
        audience="distributors",
        tone="Professional",
        target_type="business",
        niche_or_industry="health & wellness distribution",
        target_countries=["United States"],
    )


def _reason_dict(key: str, value: str, text: str = "cited fact") -> dict:
    return {"reason": text, "evidence_key": key, "evidence_value": value}


def _target_dict(name="Acme Corp", handle="acme.com", fit_reasons=None) -> dict:
    if fit_reasons is None:
        fit_reasons = [_reason_dict("industry", "Wholesale distribution")]
    return {"name": name, "handle_or_domain": handle, "fit_reasons_json": json.dumps(fit_reasons)}


class _EnvFixture:
    """Ensures GEMINI_API_KEY from the real environment never leaks into a
    "no key" test — mirrors the Slice 2/3 test pattern."""

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

    def _setup_campaign(self, name="WS") -> tuple[int, int]:
        ws = db.create_workspace(name)
        camp = db.create_campaign(ws, "promo", _brief().model_dump_json(), "business")
        return ws, camp

    def _make_target(
        self, workspace_id, campaign_id, name="Acme Corp", handle="acme.com",
        fit_reasons=None, stage="queued", fit_score=80,
    ) -> int:
        if fit_reasons is None:
            fit_reasons = [_reason_dict("industry", "Wholesale distribution")]
        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO target (workspace_id, campaign_id, source, external_id, name,
                                     handle_or_domain, reach, location, raw_json, fit_score,
                                     fit_reasons_json, stage)
                VALUES (?, ?, 'seed', NULL, ?, ?, 10, 'United States', '{}', ?, ?, ?)
                """,
                (workspace_id, campaign_id, name, handle, fit_score, json.dumps(fit_reasons), stage),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _make_draft(self, workspace_id, target_id, body=None, status="pending") -> int:
        body = body or "Hi there, this is a sample outreach draft body for testing."
        draft_id = db.add_draft(workspace_id, target_id, body, "heuristic", DraftStatus.NO_GEMINI_KEY)
        if status != "pending":
            conn = db.get_connection()
            conn.execute("UPDATE draft SET status = ? WHERE id = ?", (status, draft_id))
            conn.commit()
            conn.close()
        return draft_id


# --- Test 1: schema shape ----------------------------------------------------


class SchemaShapeTests(unittest.TestCase):
    def test_rejects_too_short_body(self):
        with self.assertRaises(ValidationError):
            OutreachDraft(body="short", evidence_key="industry", evidence_value="Wholesale")

    def test_rejects_too_long_body(self):
        with self.assertRaises(ValidationError):
            OutreachDraft(body="x" * 1501, evidence_key="industry", evidence_value="Wholesale")

    def test_rejects_blank_evidence_key_or_value(self):
        body = "Hi there, this is a perfectly reasonable outreach body."
        with self.assertRaises(ValidationError):
            OutreachDraft(body=body, evidence_key="   ", evidence_value="v")
        with self.assertRaises(ValidationError):
            OutreachDraft(body=body, evidence_key="k", evidence_value=" ")

    def test_accepts_a_normal_message(self):
        body = "Hi Acme, I noticed you work in wholesale distribution. Got a minute?"
        draft = OutreachDraft(body=body, evidence_key="industry", evidence_value="Wholesale distribution")
        self.assertEqual(draft.evidence_key, "industry")


class ValidateDraftBodyTests(unittest.TestCase):
    def test_too_short_raises(self):
        with self.assertRaises(ValueError):
            validate_draft_body("short")

    def test_too_long_raises(self):
        with self.assertRaises(ValueError):
            validate_draft_body("x" * 1501)

    def test_blank_raises(self):
        with self.assertRaises(ValueError):
            validate_draft_body("   ")

    def test_strips_and_returns_valid_text(self):
        text = "  " + "a" * 25 + "  "
        self.assertEqual(validate_draft_body(text), "a" * 25)


# --- Test 2: draft transitions -----------------------------------------------


class DraftTransitionTests(_DBFixture, unittest.TestCase):
    def test_transition_map_is_exactly_spec(self):
        self.assertEqual(
            db.DRAFT_TRANSITIONS,
            {
                "pending": {"edited", "approved", "rejected"},
                "edited": {"edited", "approved", "rejected"},
                "approved": set(),
                "rejected": set(),
            },
        )

    def test_save_on_approved_draft_raises_and_makes_no_change(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="approved")
        before = dict(db.get_draft(ws, draft_id))
        before_audit_count = len(db.list_audit(ws, camp))
        with self.assertRaises(db.InvalidTransition):
            db.save_draft_body(ws, draft_id, "y" * 25)
        self.assertEqual(dict(db.get_draft(ws, draft_id)), before)
        self.assertEqual(len(db.list_audit(ws, camp)), before_audit_count)

    def test_approve_on_rejected_draft_raises(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="rejected")
        with self.assertRaises(db.InvalidTransition):
            db.approve_draft(ws, draft_id, "y" * 25)

    def test_reject_on_approved_draft_raises(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="approved")
        with self.assertRaises(db.InvalidTransition):
            db.reject_draft(ws, draft_id)

    def test_pending_and_edited_allow_edit_approve_reject(self):
        ws, camp = self._setup_campaign()
        for start_status in ("pending", "edited"):
            target_id = self._make_target(ws, camp, name=f"T-{start_status}", handle=f"{start_status}.com")
            draft_id = self._make_draft(ws, target_id, status=start_status)
            db.save_draft_body(ws, draft_id, "y" * 25)
            self.assertEqual(db.get_draft(ws, draft_id)["status"], "edited")


# --- Test 3: stage transitions ------------------------------------------------


class StageTransitionTests(_DBFixture, unittest.TestCase):
    def _approved_target(self, stage="queued") -> tuple[int, int, int]:
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp, stage=stage)
        self._make_draft(ws, target_id, status="approved")
        return ws, camp, target_id

    def test_stage_transition_map_is_exactly_spec(self):
        self.assertEqual(
            db.STAGE_TRANSITIONS,
            {
                "queued": {"contacted", "declined"},
                "contacted": {"replied", "declined"},
                "replied": {"live", "declined"},
                "live": set(),
                "declined": set(),
            },
        )

    def test_every_legal_transition_succeeds(self):
        for old, allowed in db.STAGE_TRANSITIONS.items():
            for new in allowed:
                ws, _camp, target_id = self._approved_target(stage=old)
                self.assertTrue(db.set_target_stage(ws, target_id, new))
                self.assertEqual(db.get_target(ws, target_id)["stage"], new)

    def test_illegal_jump_raises_even_though_enum_value_is_valid(self):
        ws, _camp, target_id = self._approved_target(stage="queued")
        with self.assertRaises(db.InvalidTransition):
            db.set_target_stage(ws, target_id, "live")
        self.assertEqual(db.get_target(ws, target_id)["stage"], "queued")

    def test_same_stage_is_idempotent_no_op_with_no_audit(self):
        ws, camp, target_id = self._approved_target(stage="queued")
        before = len(db.list_audit(ws, camp))
        changed = db.set_target_stage(ws, target_id, "queued")
        self.assertFalse(changed)
        self.assertEqual(len(db.list_audit(ws, camp)), before)

    def test_route_returns_422_on_non_enum_stage(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, _camp, target_id = self._approved_target()
        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(f"/targets/{target_id}/stage", data={"stage": "not-a-real-stage"})
        self.assertEqual(resp.status_code, 422)

    def test_route_returns_422_on_non_enum_draft_action(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="pending")
        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(f"/drafts/{draft_id}/action", data={"action": "delete", "body": "x" * 25})
        self.assertEqual(resp.status_code, 422)


# --- Test 4: approving unsaved textarea text ---------------------------------


class ApproveUnsavedTextTests(_DBFixture, unittest.TestCase):
    def test_db_level_approve_with_changed_body_sets_edited_body(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, body="Hi there, the original outreach draft text.")
        db.approve_draft(ws, draft_id, "Hi there, a changed outreach draft text right here.")
        draft = db.get_draft(ws, draft_id)
        self.assertEqual(draft["status"], "approved")
        self.assertEqual(draft["edited_body"], "Hi there, a changed outreach draft text right here.")

    def test_crlf_textarea_submission_without_edit_is_not_flagged_as_edited(self):
        """A real browser <textarea> submits \\r\\n line endings regardless
        of how its value was set (HTML spec); a stored draft body uses
        plain \\n. An unedited approval must not be misread as an edit just
        because of that normalization (caught by manual browser
        verification — TestClient's form posts never exercise it)."""
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        original = "Hi there, this is the stored draft body with an\nembedded line break."
        draft_id = self._make_draft(ws, target_id, body=original)
        db.approve_draft(ws, draft_id, original.replace("\n", "\r\n"))
        draft = db.get_draft(ws, draft_id)
        self.assertEqual(draft["status"], "approved")
        approved_row = next(r for r in db.list_audit(ws, camp) if r["action"] == "draft.approved")
        self.assertIsNone(approved_row["detail"])

    def test_reverting_saved_edit_to_original_before_approve_clears_stale_edit(self):
        """Approve must commit the textarea's current text even when a prior
        Save populated edited_body and the human later reverts to body."""
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        original = "Hi there, this is the original outreach draft body."
        saved_edit = "Hi there, this is a previously saved edited outreach body."
        draft_id = self._make_draft(ws, target_id, body=original)

        db.save_draft_body(ws, draft_id, saved_edit)
        db.approve_draft(ws, draft_id, original)

        draft = db.get_draft(ws, draft_id)
        self.assertEqual(draft["status"], "approved")
        self.assertIsNone(draft["edited_body"])
        self.assertEqual(db.list_pipeline_targets(ws)[0]["draft_text"], original)
        approved_row = next(
            r for r in db.list_audit(ws, camp) if r["action"] == "draft.approved"
        )
        self.assertIsNone(approved_row["detail"])

    def test_route_level_approve_without_save_shows_changed_text_on_pipeline(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, body="Hi there, the original outreach draft text.")
        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(
                f"/drafts/{draft_id}/action",
                data={"action": "approve", "body": "Hi there, an unsaved changed outreach text."},
                follow_redirects=False,
            )
            self.assertEqual(resp.status_code, 303)
            page = client.get("/pipeline")
        self.assertIn("Hi there, an unsaved changed outreach text.", page.text)


# --- Test 5: runtime evidence grounding for LLM drafts -----------------------


class DraftGroundingTests(_EnvFixture, unittest.TestCase):
    def test_valid_cited_pair_used_in_body_is_kept(self):
        target = _target_dict(fit_reasons=[_reason_dict("industry", "Wholesale distribution")])
        draft = OutreachDraft(
            body="Hi Acme Corp, I noticed you work in Wholesale distribution. Got a minute?",
            evidence_key="industry",
            evidence_value="Wholesale distribution",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=draft):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.LLM_OK)
        self.assertEqual(result.body, draft.body)
        self.assertEqual(result.model_used, llm.GEMINI_MODEL)

    def test_fabricated_pair_falls_back_to_heuristic(self):
        target = _target_dict(fit_reasons=[_reason_dict("industry", "Wholesale distribution")])
        draft = OutreachDraft(
            body="Hi Acme Corp, I saw that you have about 9999 people. Got a minute?",
            evidence_key="employees",
            evidence_value="9999",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=draft):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.HEURISTIC_FALLBACK)
        self.assertEqual(result.model_used, "heuristic")
        self.assertEqual(result.reason, "model draft did not pass the grounding check")

    def test_pair_belonging_to_another_target_falls_back(self):
        target = _target_dict(fit_reasons=[_reason_dict("industry", "Wholesale distribution")])
        draft = OutreachDraft(
            body="Hi Acme Corp, I noticed you work in Consumer mobile apps. Got a minute?",
            evidence_key="industry",
            evidence_value="Consumer mobile apps",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=draft):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.HEURISTIC_FALLBACK)

    def test_body_omitting_its_claimed_value_falls_back(self):
        target = _target_dict(fit_reasons=[_reason_dict("industry", "Wholesale distribution")])
        draft = OutreachDraft(
            body="Hi Acme Corp, hope you're doing well and would love to set up a quick call.",
            evidence_key="industry",
            evidence_value="Wholesale distribution",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=draft):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.HEURISTIC_FALLBACK)


# --- Test 6: unknown-name / domain identity handling -------------------------


class IdentityGroundingTests(_EnvFixture, unittest.TestCase):
    def test_meaningful_name_must_be_referenced(self):
        target = _target_dict(
            name="Acme Corp", handle="acme.com",
            fit_reasons=[_reason_dict("industry", "Wholesale distribution")],
        )
        draft = OutreachDraft(
            body="Hi there, I noticed you work in Wholesale distribution recently, got a minute?",
            evidence_key="industry",
            evidence_value="Wholesale distribution",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=draft):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.HEURISTIC_FALLBACK)  # never names Acme Corp

    def test_default_name_falls_back_to_domain(self):
        target = _target_dict(
            name=DEFAULT_NAME, handle="acme.com",
            fit_reasons=[_reason_dict("industry", "Wholesale distribution")],
        )
        draft = OutreachDraft(
            body="Hi acme.com team, I noticed you work in Wholesale distribution. Got a minute?",
            evidence_key="industry",
            evidence_value="Wholesale distribution",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=draft):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.LLM_OK)

    def test_no_identity_skips_identity_check_but_still_requires_grounding(self):
        target = _target_dict(
            name=DEFAULT_NAME, handle=None,
            fit_reasons=[_reason_dict("industry", "Wholesale distribution")],
        )
        grounded = OutreachDraft(
            body="Hi there, I noticed this company works in Wholesale distribution. Got a minute?",
            evidence_key="industry",
            evidence_value="Wholesale distribution",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=grounded):
            result = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.LLM_OK)

        ungrounded = OutreachDraft(
            body="Hi there, hope you're doing well and would love to set up a quick call soon.",
            evidence_key="industry",
            evidence_value="Wholesale distribution",
        )
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=ungrounded):
            result2 = drafting.draft_outreach(_brief(), target, {"gemini": "fake"})
        self.assertEqual(result2.status, DraftStatus.HEURISTIC_FALLBACK)


# --- Test 7: negative evidence -> neutral heuristic prose --------------------


class NegativeEvidenceHeuristicTests(_EnvFixture, unittest.TestCase):
    def test_poor_fit_reason_is_stated_neutrally(self):
        target = _target_dict(
            name="Mismatch Inc", handle="mismatch.com",
            fit_reasons=[
                _reason_dict(
                    "industry", "Consumer mobile apps",
                    text="Industry doesn't match the brief's niche",
                )
            ],
        )
        result = drafting.draft_outreach(_brief(), target, {})  # no key -> heuristic
        self.assertEqual(result.status, DraftStatus.NO_GEMINI_KEY)
        self.assertEqual(result.model_used, "heuristic")
        body_lower = result.body.lower()
        self.assertIn("consumer mobile apps", body_lower)
        self.assertIn("mismatch inc", body_lower)
        for phrase in ("ideal partner", "perfect fit", "right size", "targeted market"):
            self.assertNotIn(phrase, body_lower)


# --- Test 8: credential paths -------------------------------------------------


class CredentialPathTests(_EnvFixture, unittest.TestCase):
    def test_no_key_returns_heuristic(self):
        result = drafting.draft_outreach(_brief(), _target_dict(), {})
        self.assertEqual(result.status, DraftStatus.NO_GEMINI_KEY)
        self.assertEqual(result.model_used, "heuristic")

    def test_invalid_key_returns_heuristic_with_reason(self):
        with mock.patch(
            "app.agent.drafting.llm.generate_structured",
            side_effect=llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "bad key"),
        ):
            result = drafting.draft_outreach(_brief(), _target_dict(), {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.INVALID_GEMINI_KEY)
        self.assertEqual(result.reason, "bad key")
        self.assertEqual(result.model_used, "heuristic")

    def test_provider_error_returns_heuristic(self):
        with mock.patch(
            "app.agent.drafting.llm.generate_structured",
            side_effect=llm.LLMError(llm.LLMErrorKind.ERROR, "boom"),
        ):
            result = drafting.draft_outreach(_brief(), _target_dict(), {"gemini": "fake"})
        self.assertEqual(result.status, DraftStatus.GEMINI_ERROR)
        self.assertEqual(result.model_used, "heuristic")

    def test_known_invalid_key_reason_skips_the_live_call(self):
        with mock.patch("app.agent.drafting.llm.generate_structured") as gen:
            result = drafting.draft_outreach(
                _brief(), _target_dict(), {"gemini": "fake"}, known_invalid_key_reason="already rejected"
            )
        gen.assert_not_called()
        self.assertEqual(result.status, DraftStatus.INVALID_GEMINI_KEY)
        self.assertEqual(result.reason, "already rejected")

    def test_never_raises(self):
        with mock.patch("app.agent.drafting.llm.generate_structured", return_value=None):
            drafting.draft_outreach(_brief(), _target_dict(), {"gemini": "fake"})
        with mock.patch(
            "app.agent.drafting.llm.generate_structured",
            side_effect=llm.LLMError(llm.LLMErrorKind.INVALID_KEY, "x"),
        ):
            drafting.draft_outreach(_brief(), _target_dict(), {"gemini": "fake"})
        with mock.patch(
            "app.agent.drafting.llm.generate_structured",
            side_effect=llm.LLMError(llm.LLMErrorKind.ERROR, "x"),
        ):
            drafting.draft_outreach(_brief(), _target_dict(), {"gemini": "fake"})


# --- Test 9: re-draft after rejection -----------------------------------------


class RedraftAfterRejectionTests(_DBFixture, unittest.TestCase):
    def test_active_draft_ignores_a_rejected_draft(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._make_draft(ws, target_id, status="rejected")
        self.assertIsNone(db.get_active_draft_for_target(ws, target_id))

    def test_new_draft_after_rejection_succeeds(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._make_draft(ws, target_id, status="rejected")
        new_id = db.add_draft(
            ws, target_id, "Hi there, another try at outreach text goes here.", "heuristic",
            DraftStatus.NO_GEMINI_KEY,
        )
        self.assertIsNotNone(db.get_draft(ws, new_id))

    def test_campaign_detail_cta_is_draft_again_after_rejection(self):
        from app.main import _draft_cta

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._make_draft(ws, target_id, status="rejected")
        latest = db.get_latest_draft_for_target(ws, target_id)
        self.assertEqual(_draft_cta(target_id, latest)["label"], "Draft again")


# --- Test 10: one-active-draft concurrency / uniqueness ----------------------


class ActiveDraftUniquenessTests(_DBFixture, unittest.TestCase):
    def test_second_draft_while_active_raises_active_draft_exists(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        db.add_draft(ws, target_id, "Hi there, first draft text goes here today.", "heuristic", DraftStatus.NO_GEMINI_KEY)
        with self.assertRaises(db.ActiveDraftExists):
            db.add_draft(
                ws, target_id, "Hi there, second draft text goes here today.", "heuristic",
                DraftStatus.NO_GEMINI_KEY,
            )

    def test_is_active_draft_conflict_matches_only_the_unique_index(self):
        unique_exc = sqlite3.IntegrityError("UNIQUE constraint failed: draft.workspace_id, draft.target_id")
        fk_exc = sqlite3.IntegrityError("FOREIGN KEY constraint failed")
        self.assertTrue(db._is_active_draft_conflict(unique_exc))
        self.assertFalse(db._is_active_draft_conflict(fk_exc))

    def test_route_maps_active_draft_exists_to_approvals_redirect(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        db.add_draft(ws, target_id, "Hi there, existing draft text goes here today.", "heuristic", DraftStatus.NO_GEMINI_KEY)
        with TestClient(app) as client, mock.patch(
            "app.main.drafting.draft_outreach",
            return_value=DraftResult("Hi there, second attempt text.", "heuristic", DraftStatus.NO_GEMINI_KEY, None),
        ):
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(f"/targets/{target_id}/draft", follow_redirects=False)
        # The route's own memory/UX check catches this before add_draft runs.
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/approvals")


# --- Test 11: pipeline target deduplication ----------------------------------


class PipelineDedupTests(_DBFixture, unittest.TestCase):
    def test_target_appears_once_with_the_latest_approved_text(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        d1 = self._make_draft(ws, target_id, body="Hi there, first version of the outreach text.", status="approved")
        conn = db.get_connection()
        conn.execute("UPDATE draft SET status = 'rejected' WHERE id = ?", (d1,))
        conn.commit()
        conn.close()
        d2 = self._make_draft(ws, target_id, body="Hi there, second and current version of text.", status="approved")

        rows = db.list_pipeline_targets(ws)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["draft_id"], d2)
        self.assertEqual(rows[0]["draft_text"], "Hi there, second and current version of text.")

    def test_unapproved_target_never_appears(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self._make_draft(ws, target_id, status="pending")
        self.assertEqual(db.list_pipeline_targets(ws), [])


# --- Test 12: DB-boundary tenant isolation ------------------------------------


class TenantIsolationTests(_DBFixture, unittest.TestCase):
    def test_add_draft_for_other_workspace_target_raises_not_found(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        with self.assertRaises(db.NotFound):
            db.add_draft(
                ws_b, target_id, "Hi there, cross workspace draft text here.", "heuristic",
                DraftStatus.NO_GEMINI_KEY,
            )
        self.assertIsNone(db.get_active_draft_for_target(ws_b, target_id))

    def test_cross_workspace_draft_cannot_be_read_or_mutated(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        draft_id = self._make_draft(ws_a, target_id)

        self.assertIsNone(db.get_draft(ws_b, draft_id))
        with self.assertRaises(db.NotFound):
            db.save_draft_body(ws_b, draft_id, "y" * 25)
        with self.assertRaises(db.NotFound):
            db.approve_draft(ws_b, draft_id, "y" * 25)
        with self.assertRaises(db.NotFound):
            db.reject_draft(ws_b, draft_id)
        with self.assertRaises(db.NotFound):
            db.set_target_stage(ws_b, target_id, "contacted")

    def test_second_workspace_sees_none_of_the_first(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        self._make_draft(ws_a, target_id, status="approved")

        self.assertEqual(db.list_pending_drafts(ws_b), [])
        self.assertEqual(db.list_pipeline_targets(ws_b), [])


# --- Test 13: atomic mutation + audit -----------------------------------------


class AtomicMutationAuditTests(_DBFixture, unittest.TestCase):
    def test_each_mutation_writes_exactly_one_correctly_scoped_audit_row(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = db.add_draft(
            ws, target_id, "Hi there, initial outreach draft text right here.", "heuristic",
            DraftStatus.NO_GEMINI_KEY,
        )
        self.assertEqual(len(db.list_audit(ws, camp)), 1)

        db.save_draft_body(ws, draft_id, "Hi there, an edited outreach draft text here.")
        self.assertEqual(len(db.list_audit(ws, camp)), 2)

        db.approve_draft(ws, draft_id, "Hi there, an edited outreach draft text here.")
        self.assertEqual(len(db.list_audit(ws, camp)), 3)

        db.set_target_stage(ws, target_id, "contacted")
        self.assertEqual(len(db.list_audit(ws, camp)), 4)

        rows = db.list_audit(ws, camp)
        self.assertEqual(
            [r["action"] for r in rows],
            ["draft.created", "draft.edited", "draft.approved", "target.stage_changed"],
        )
        for row in rows:
            self.assertEqual(row["workspace_id"], ws)
            self.assertEqual(row["campaign_id"], camp)
            self.assertEqual(row["target_id"], target_id)

    def test_illegal_transition_leaves_no_change_and_no_audit(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="approved")
        before_count = len(db.list_audit(ws, camp))
        with self.assertRaises(db.InvalidTransition):
            db.approve_draft(ws, draft_id, "y" * 25)
        self.assertEqual(len(db.list_audit(ws, camp)), before_count)
        self.assertEqual(db.get_draft(ws, draft_id)["status"], "approved")


# --- Test 14: lifecycle CTA mapping -------------------------------------------


class LifecycleCtaTests(unittest.TestCase):
    def test_no_draft_yields_draft_outreach(self):
        from app.main import _draft_cta

        self.assertEqual(_draft_cta(1, None), {"kind": "draft", "label": "Draft outreach"})

    def test_rejected_yields_draft_again(self):
        from app.main import _draft_cta

        row = {"status": "rejected", "id": 5}
        self.assertEqual(_draft_cta(1, row), {"kind": "draft", "label": "Draft again"})

    def test_pending_or_edited_links_to_approvals(self):
        from app.main import _draft_cta

        for status in ("pending", "edited"):
            cta = _draft_cta(1, {"status": status, "id": 5})
            self.assertEqual(cta["kind"], "approvals")
            self.assertEqual(cta["href"], "/approvals#draft-5")

    def test_approved_links_to_pipeline_never_approvals(self):
        from app.main import _draft_cta

        cta = _draft_cta(9, {"status": "approved", "id": 5})
        self.assertEqual(cta["kind"], "pipeline")
        self.assertEqual(cta["href"], "/pipeline#target-9")


# --- Test 15: nothing sends ----------------------------------------------------


class NothingSendsTests(_DBFixture, unittest.TestCase):
    def test_approve_reject_and_stage_never_call_httpx(self):
        ws, camp = self._setup_campaign()
        target_a = self._make_target(ws, camp, name="A", handle="a.com")
        target_b = self._make_target(ws, camp, name="B", handle="b.com")
        draft_a = self._make_draft(ws, target_a, status="pending")
        draft_b = self._make_draft(ws, target_b, status="pending")

        with mock.patch("httpx.post") as post, mock.patch("httpx.get") as get:
            db.approve_draft(ws, draft_a, "Hi there, approved outreach text goes here.")
            db.set_target_stage(ws, target_a, "contacted")
            db.reject_draft(ws, draft_b)
            post.assert_not_called()
            get.assert_not_called()


# --- Test 16: unapproved target cannot be advanced by direct POST ------------


class UnapprovedTargetStageTests(_DBFixture, unittest.TestCase):
    def test_no_draft_target_cannot_move(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self.assertFalse(db.has_approved_draft(ws, target_id))
        for stage in db.STAGE_TRANSITIONS["queued"]:
            with self.assertRaises(db.NotFound):
                db.set_target_stage(ws, target_id, stage)
        self.assertEqual(db.get_target(ws, target_id)["stage"], "queued")
        self.assertEqual(len(db.list_audit(ws, camp)), 0)

    def test_pending_edited_or_rejected_draft_cannot_move(self):
        ws, camp = self._setup_campaign()
        for status in ("pending", "edited", "rejected"):
            target_id = self._make_target(ws, camp, name=f"T-{status}", handle=f"{status}.com")
            self._make_draft(ws, target_id, status=status)
            self.assertFalse(db.has_approved_draft(ws, target_id))
            with self.assertRaises(db.NotFound):
                db.set_target_stage(ws, target_id, "contacted")

    def test_has_approved_draft_agrees_with_the_stage_gate(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        self.assertFalse(db.has_approved_draft(ws, target_id))
        with self.assertRaises(db.NotFound):
            db.set_target_stage(ws, target_id, "contacted")
        self._make_draft(ws, target_id, status="approved")
        self.assertTrue(db.has_approved_draft(ws, target_id))
        self.assertTrue(db.set_target_stage(ws, target_id, "contacted"))

    def test_route_level_no_mutation_and_no_audit(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(f"/targets/{target_id}/stage", data={"stage": "contacted"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/pipeline")
        self.assertEqual(db.get_target(ws, target_id)["stage"], "queued")
        self.assertEqual(len(db.list_audit(ws, camp)), 0)


# --- Test 17: scoped target/brief loader --------------------------------------


class ScopedTargetBriefLoaderTests(_DBFixture, unittest.TestCase):
    def test_get_target_none_for_cross_workspace_or_missing(self):
        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        self.assertIsNone(db.get_target(ws_b, target_id))
        self.assertIsNone(db.get_target(ws_a, 999999))

    def test_route_redirects_without_creating_a_draft_for_cross_workspace_target(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws_a, camp_a = self._setup_campaign("A")
        ws_b, _camp_b = self._setup_campaign("B")
        target_id = self._make_target(ws_a, camp_a)
        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws_b))
            resp = client.post(f"/targets/{target_id}/draft", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/campaigns")
        self.assertIsNone(db.get_active_draft_for_target(ws_a, target_id))

    def test_route_passes_the_campaigns_persisted_brief_to_drafting(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        captured = {}

        def fake_draft_outreach(brief, target, settings, **kwargs):
            captured["brief"] = brief
            captured["target_id"] = target.get("id")
            return DraftResult("Hi there, captured outreach text goes here.", "heuristic", DraftStatus.NO_GEMINI_KEY, None)

        with TestClient(app) as client, mock.patch(
            "app.main.drafting.draft_outreach", side_effect=fake_draft_outreach
        ):
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(f"/targets/{target_id}/draft", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)

        campaign = db.get_campaign(ws, camp)
        expected_brief = Brief.model_validate_json(campaign["brief_json"])
        self.assertEqual(captured["brief"], expected_brief)
        self.assertEqual(captured["target_id"], target_id)


# --- Test 18: human-submitted body validation ---------------------------------


class HumanBodyValidationTests(_DBFixture, unittest.TestCase):
    def test_save_and_approve_raise_invalid_draft_body(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="pending")
        for bad in ("", "   ", "x" * 1501):
            with self.assertRaises(db.InvalidDraftBody):
                db.save_draft_body(ws, draft_id, bad)
            with self.assertRaises(db.InvalidDraftBody):
                db.approve_draft(ws, draft_id, bad)
        self.assertEqual(db.get_draft(ws, draft_id)["status"], "pending")
        self.assertEqual(len(db.list_audit(ws, camp)), 1)  # only draft.created

    def test_reject_ignores_body_entirely(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="pending")
        db.reject_draft(ws, draft_id)
        self.assertEqual(db.get_draft(ws, draft_id)["status"], "rejected")

    def test_route_returns_422_for_blank_approve_body(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="pending")
        with TestClient(app) as client:
            client.cookies.set("workspace_id", str(ws))
            resp = client.post(f"/drafts/{draft_id}/action", data={"action": "approve", "body": ""})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(db.get_draft(ws, draft_id)["status"], "pending")


# --- Test 19: draft.created audit explains the outcome -----------------------


class DraftCreatedAuditExplainsOutcomeTests(_DBFixture, unittest.TestCase):
    def test_each_status_produces_a_distinguishable_detail(self):
        ws, camp = self._setup_campaign()
        cases = [
            (DraftStatus.LLM_OK, None, "llm_ok"),
            (DraftStatus.NO_GEMINI_KEY, None, "no_gemini_key"),
            (DraftStatus.INVALID_GEMINI_KEY, "bad key", "invalid_gemini_key: bad key"),
            (DraftStatus.GEMINI_ERROR, "boom", "gemini_error: boom"),
            (
                DraftStatus.HEURISTIC_FALLBACK,
                "model draft did not pass the grounding check",
                "heuristic_fallback: model draft did not pass the grounding check",
            ),
        ]
        for i, (status, reason, expected_detail) in enumerate(cases):
            target_id = self._make_target(ws, camp, name=f"Target {i}", handle=f"t{i}.com")
            draft_id = db.add_draft(
                ws, target_id, "Hi there, outreach draft body text goes here.", "heuristic", status, reason
            )
            row = next(r for r in db.list_audit(ws, camp) if r["draft_id"] == draft_id)
            self.assertEqual(row["action"], "draft.created")
            self.assertEqual(row["detail"], expected_detail)

    def test_route_distinguishes_grounding_fallback_from_no_key(self):
        from fastapi.testclient import TestClient

        from app.main import app

        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        with TestClient(app) as client, mock.patch(
            "app.main.drafting.draft_outreach",
            return_value=DraftResult(
                "Hi there, heuristic fallback outreach body text.",
                "heuristic",
                DraftStatus.HEURISTIC_FALLBACK,
                "model draft did not pass the grounding check",
            ),
        ):
            client.cookies.set("workspace_id", str(ws))
            client.post(f"/targets/{target_id}/draft", follow_redirects=False)
        detail = next(r["detail"] for r in db.list_audit(ws, camp) if r["action"] == "draft.created")
        self.assertIn("heuristic_fallback", detail)
        self.assertNotIn("no_gemini_key", detail)


# --- Tests 20-21: real concurrency, two separate sqlite3 connections --------


class ConcurrentDraftActionTests(_DBFixture, unittest.TestCase):
    def test_concurrent_approve_produces_exactly_one_approval(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, body="Hi there, the original outreach draft body.")

        barrier = threading.Barrier(2)
        results = {}

        def worker(name, body):
            try:
                barrier.wait(timeout=5)
                db.approve_draft(ws, draft_id, body)
                results[name] = "ok"
            except db.InvalidTransition:
                results[name] = "invalid_transition"

        body_a = "Hi there, version A of the outreach body text."
        body_b = "Hi there, version B of the outreach body text."
        t1 = threading.Thread(target=worker, args=("a", body_a))
        t2 = threading.Thread(target=worker, args=("b", body_b))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        outcomes = list(results.values())
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("invalid_transition"), 1)

        draft = db.get_draft(ws, draft_id)
        self.assertEqual(draft["status"], "approved")
        approved_rows = [r for r in db.list_audit(ws, camp) if r["action"] == "draft.approved"]
        self.assertEqual(len(approved_rows), 1)
        winner_body = body_a if results["a"] == "ok" else body_b
        self.assertEqual(draft["edited_body"], winner_body)

    def test_concurrent_reject_produces_exactly_one_rejection(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="pending")

        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def worker():
            try:
                barrier.wait(timeout=5)
                db.reject_draft(ws, draft_id)
                with lock:
                    results.append("ok")
            except db.InvalidTransition:
                with lock:
                    results.append("invalid_transition")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("invalid_transition"), 1)
        rejected_rows = [r for r in db.list_audit(ws, camp) if r["action"] == "draft.rejected"]
        self.assertEqual(len(rejected_rows), 1)

    def test_concurrent_approve_and_reject_exactly_one_terminal_state_wins(self):
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp)
        draft_id = self._make_draft(ws, target_id, status="pending")

        barrier = threading.Barrier(2)
        results = {}

        def approve_worker():
            try:
                barrier.wait(timeout=5)
                db.approve_draft(ws, draft_id, "Hi there, approved outreach body text right here.")
                results["approve"] = "ok"
            except db.InvalidTransition:
                results["approve"] = "invalid_transition"

        def reject_worker():
            try:
                barrier.wait(timeout=5)
                db.reject_draft(ws, draft_id)
                results["reject"] = "ok"
            except db.InvalidTransition:
                results["reject"] = "invalid_transition"

        t1 = threading.Thread(target=approve_worker)
        t2 = threading.Thread(target=reject_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(list(results.values()).count("ok"), 1)
        final_status = db.get_draft(ws, draft_id)["status"]
        self.assertIn(final_status, ("approved", "rejected"))


class ConcurrentStageTests(_DBFixture, unittest.TestCase):
    def _setup_approved_target(self) -> tuple[int, int, int]:
        ws, camp = self._setup_campaign()
        target_id = self._make_target(ws, camp, stage="queued")
        self._make_draft(ws, target_id, status="approved")
        return ws, camp, target_id

    def test_same_stage_race_exactly_one_success(self):
        ws, camp, target_id = self._setup_approved_target()
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def worker():
            barrier.wait(timeout=5)
            changed = db.set_target_stage(ws, target_id, "contacted")
            with lock:
                results.append(changed)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 1)
        self.assertEqual(db.get_target(ws, target_id)["stage"], "contacted")
        rows = [r for r in db.list_audit(ws, camp) if r["action"] == "target.stage_changed"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["detail"], "queued -> contacted")

    def test_contacted_declined_race_yields_a_valid_serial_history(self):
        ws, camp, target_id = self._setup_approved_target()
        barrier = threading.Barrier(2)
        results = {}

        def worker(name, stage):
            barrier.wait(timeout=5)
            try:
                changed = db.set_target_stage(ws, target_id, stage)
                results[name] = ("ok", changed)
            except db.InvalidTransition:
                results[name] = ("invalid", None)

        t1 = threading.Thread(target=worker, args=("contacted", "contacted"))
        t2 = threading.Thread(target=worker, args=("declined", "declined"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        final_stage = db.get_target(ws, target_id)["stage"]
        details = [r["detail"] for r in db.list_audit(ws, camp) if r["action"] == "target.stage_changed"]

        if results["declined"][0] == "ok" and results["contacted"][0] == "invalid":
            self.assertEqual(final_stage, "declined")
            self.assertEqual(details, ["queued -> declined"])
        elif results["contacted"][0] == "ok" and results["declined"][0] == "ok":
            self.assertEqual(final_stage, "declined")
            self.assertEqual(details, ["queued -> contacted", "contacted -> declined"])
        else:
            self.fail(f"unexpected outcome combination: {results}")


if __name__ == "__main__":
    unittest.main()
