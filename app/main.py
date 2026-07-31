"""Outpost FastAPI application.

Slice 1: workspaces (create, switch) and per-workspace BYO-key settings.
Slice 2: campaign intake and B2B discovery (Apollo, or seeded demo data).
The active workspace is tracked in a cookie; every data-touching route
depends on get_current_workspace to scope its queries.
"""

import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import audit_banners, db, sources
from app.agent import drafting, intake, scoring
from app.models import Brief, TargetType

# Literal mirrors of app.db's STAGES/DRAFT_STATUSES tuples, so FastAPI
# returns a controlled 422 on a malformed enum value before it ever reaches
# the transition-map guard in app.db.
DraftAction = Literal["save", "approve", "reject"]
PipelineStage = Literal["queued", "contacted", "replied", "live", "declined"]

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_COOKIE = "workspace_id"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup so a fresh checkout just works.
    db.init()
    yield


app = FastAPI(title="Outpost", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def get_current_workspace(
    workspace_id: str | None = Cookie(default=None),
) -> sqlite3.Row | None:
    """Resolve the active workspace from the cookie.

    Returns None if there are no workspaces yet, or if the cookie is
    missing/invalid — callers redirect to workspace creation in that case.
    Falls back to the most recently created workspace when the cookie is
    absent or stale, so a fresh browser still lands somewhere sensible.
    """
    workspaces = db.list_workspaces()
    if not workspaces:
        return None

    if workspace_id is not None:
        try:
            match = db.get_workspace(int(workspace_id))
        except ValueError:
            match = None
        if match is not None:
            return match

    return workspaces[0]


def nav_context(workspace) -> dict:
    """Shared per-request template context: the current workspace, every
    workspace (for the switcher), and the Approvals queue count shown as a
    nav pill on every page."""
    return {
        "workspace": workspace,
        "workspaces": db.list_workspaces(),
        "approvals_count": len(db.list_pending_drafts(workspace["id"])) if workspace is not None else 0,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    workspace=Depends(get_current_workspace),
) -> HTMLResponse:
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)
    return templates.TemplateResponse(request, "index.html", nav_context(workspace))


@app.get("/workspaces/new", response_class=HTMLResponse)
def new_workspace_form(
    request: Request,
    workspace=Depends(get_current_workspace),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "workspaces_new.html", nav_context(workspace))


@app.post("/workspaces")
def create_workspace(name: str = Form(...)) -> RedirectResponse:
    workspace_id = db.create_workspace(name.strip())
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(WORKSPACE_COOKIE, str(workspace_id))
    return response


@app.post("/workspaces/switch")
def switch_workspace(workspace_id: str = Form(...)) -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(WORKSPACE_COOKIE, workspace_id)
    return response


@app.get("/settings")
def settings_page(
    request: Request,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    saved = db.get_settings(workspace["id"])
    masked = {key: _mask(value) for key, value in saved.items()}
    return templates.TemplateResponse(
        request,
        "settings.html",
        {**nav_context(workspace), "setting_keys": db.SETTING_KEYS, "masked": masked},
    )


@app.post("/settings")
def save_settings(
    workspace=Depends(get_current_workspace),
    youtube: str = Form(default=""),
    apify: str = Form(default=""),
    apollo: str = Form(default=""),
    gemini: str = Form(default=""),
) -> RedirectResponse:
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    submitted = {"youtube": youtube, "apify": apify, "apollo": apollo, "gemini": gemini}
    for key_name, key_value in submitted.items():
        # Blank means "leave unchanged" — the field shows a masked
        # placeholder, not the real value, so an empty submit must not
        # overwrite the saved key with an empty string.
        if key_value.strip():
            db.save_setting(workspace["id"], key_name, key_value.strip())

    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/delete/{key_name}")
def delete_setting(
    key_name: str,
    workspace=Depends(get_current_workspace),
) -> RedirectResponse:
    if workspace is not None and key_name in db.SETTING_KEYS:
        db.delete_setting(workspace["id"], key_name)
    return RedirectResponse("/settings", status_code=303)


def _mask(value: str) -> str:
    """Mask a secret for display: dots plus the last 4 characters."""
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]


# --- Campaigns and discovery --------------------------------------------


@app.get("/campaigns")
def campaigns_list(
    request: Request,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    campaigns = db.list_campaigns(workspace["id"])
    return templates.TemplateResponse(
        request, "campaigns_list.html", {**nav_context(workspace), "campaigns": campaigns}
    )


@app.get("/campaigns/new")
def new_campaign_form(
    request: Request,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    return templates.TemplateResponse(request, "campaign_new.html", nav_context(workspace))


@app.post("/campaigns")
def create_campaign(
    # target_type is typed with the shared TargetType literal, so FastAPI
    # returns a controlled 422 for any value other than creator/business
    # rather than letting an unknown value reach (and KeyError) the audit maps.
    promoting_what: str = Form(...),
    target_type: TargetType = Form(...),
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    cleaned_promoting_what = promoting_what.strip()
    if not cleaned_promoting_what:
        # Empty/whitespace intake is a controlled 4xx, never a 500 downstream.
        raise HTTPException(status_code=422, detail="Describe what you're promoting.")

    workspace_id = workspace["id"]
    settings = db.get_settings(workspace_id)

    # 1. Parse the Brief and retain IntakeStatus.
    intake_result = intake.parse_brief(cleaned_promoting_what, target_type, settings)

    # 2. Create the campaign and obtain campaign_id.
    campaign_id = db.create_campaign(
        workspace_id, cleaned_promoting_what, intake_result.brief.model_dump_json(), target_type
    )

    # 3. Write the intake audit row with workspace_id and campaign_id.
    intake_action, _, _ = audit_banners.INTAKE_MAP[intake_result.status]
    db.add_audit(workspace_id, campaign_id, "agent", intake_action, detail=intake_result.reason)

    # 4. Run discovery.
    discovery_result = sources.discover(intake_result.brief, settings)

    # 5. Write the discovery audit row with workspace_id and campaign_id.
    discovery_action, _, _ = audit_banners.DISCOVERY_MAP[discovery_result.status]
    db.add_audit(workspace_id, campaign_id, "agent", discovery_action, detail=discovery_result.reason)

    # 6. Zero-target branch: nothing to score or persist. A neutral audit
    # record, not a status->banner mapping, so it renders no banner.
    if not discovery_result.candidates:
        db.add_audit(workspace_id, campaign_id, "agent", "scoring.skipped_no_targets", detail=None)
        return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)

    # 7. Build normalized, source-neutral evidence for every candidate
    # through the Source.evidence() boundary (never provider-specific keys).
    evidence_list = [
        sources.evidence_for(discovery_result.source_used, c) for c in discovery_result.candidates
    ]

    # 8. Score the whole batch in one LLM call (bounded latency; a rejected
    # credential is a single 403, never a per-target retry loop). If intake
    # already learned this same Gemini key is rejected, don't ask it again.
    known_invalid_reason = (
        intake_result.reason
        if intake_result.status == intake.IntakeStatus.INVALID_GEMINI_KEY
        else None
    )
    score_outcome = scoring.score_batch(
        intake_result.brief, evidence_list, settings,
        known_invalid_key_reason=known_invalid_reason,
    )

    # 9. Defense-in-depth: confirm every score has a grounded citation
    # before it ever reaches the database — a second, independent check
    # beyond score_batch's own internal guarantee (Slice 3 hardening).
    scoring.assert_grounded(evidence_list, score_outcome.scores)

    # 10. Persist targets and their fit scores together, in one transaction —
    # a campaign is never left partially scored.
    db.add_scored_targets(
        workspace_id,
        campaign_id,
        discovery_result.candidates,
        discovery_result.source_used,
        score_outcome.scores,
    )

    # 11. Write ONE scoring audit row from the honest aggregate outcome.
    scoring_action, _, _ = audit_banners.SCORING_MAP[score_outcome.status]
    db.add_audit(workspace_id, campaign_id, "agent", scoring_action, detail=score_outcome.reason)

    # 12. Redirect to the campaign-detail route.
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)


def _fit_class(fit_score: int | None) -> str | None:
    """Design.md's fit-score coloring band, computed here so the template
    stays logic-light: >=85 success, 70-84 text, <70 text-3."""
    if fit_score is None:
        return None
    if fit_score >= 85:
        return "fit--high"
    if fit_score >= 70:
        return "fit--mid"
    return "fit--low"


@app.get("/campaigns/{campaign_id}")
def campaign_detail(
    campaign_id: int,
    request: Request,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    workspace_id = workspace["id"]
    campaign = db.get_campaign(workspace_id, campaign_id)
    if campaign is None:
        return RedirectResponse("/campaigns", status_code=303)

    brief = json.loads(campaign["brief_json"])
    # The table shows only the country portion of each target's location
    # (design.md's Company/Domain/Country/Size/Source columns); the raw
    # source payload already carries a "country" field for both Apollo and
    # seed candidates.
    targets = []
    for t in db.list_targets(workspace_id, campaign_id):
        raw = json.loads(t["raw_json"]) if t["raw_json"] else {}
        fit_reasons = json.loads(t["fit_reasons_json"]) if t["fit_reasons_json"] else []
        latest_draft = db.get_latest_draft_for_target(workspace_id, t["id"])
        targets.append(
            {
                **dict(t),
                "country": raw.get("country"),
                "fit_reasons": fit_reasons,
                "fit_class": _fit_class(t["fit_score"]),
                "cta": _draft_cta(t["id"], latest_draft),
            }
        )

    # Banners are re-derived from the audit trail, not passed through the
    # URL — the most recent intake.*/discovery.*/scoring.* rows for this campaign.
    banners = []
    activity = []
    for row in db.list_audit(workspace_id, campaign_id):
        if (
            row["action"].startswith("intake.")
            or row["action"].startswith("discovery.")
            or row["action"].startswith("scoring.")
        ):
            banner = audit_banners.banner_for(row["action"], row["detail"])
            if banner is not None:
                banners.append(banner)
        activity.append(
            {
                "label": audit_banners.label_for(row["action"]),
                "detail": row["detail"],
                "created_at": row["created_at"],
            }
        )
    activity.reverse()  # newest first, for a readable Activity feed

    return templates.TemplateResponse(
        request,
        "campaign_detail.html",
        {
            **nav_context(workspace),
            "campaign": campaign,
            "brief": brief,
            "targets": targets,
            "banners": banners,
            "activity": activity,
        },
    )


def _draft_cta(target_id: int, latest_draft) -> dict:
    """Maps a target's latest-draft state to a lifecycle call-to-action
    (docs/plans/completed/SLICE_4_PLAN.md §6.2): Draft outreach / Draft again / a link to the
    active draft in Approvals / a link to the target on Pipeline. Never
    links an approved or rejected draft to a queue page that excludes it.
    """
    if latest_draft is None:
        return {"kind": "draft", "label": "Draft outreach"}
    if latest_draft["status"] == "rejected":
        return {"kind": "draft", "label": "Draft again"}
    if latest_draft["status"] == "approved":
        return {"kind": "pipeline", "label": "View on Pipeline", "href": f"/pipeline#target-{target_id}"}
    return {
        "kind": "approvals",
        "label": "View in Approvals",
        "href": f"/approvals#draft-{latest_draft['id']}",
    }


# --- Drafting, approvals, pipeline (Slice 4) --------------------------------


@app.post("/targets/{target_id}/draft")
def create_draft(
    target_id: int,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)
    workspace_id = workspace["id"]

    target = db.get_target(workspace_id, target_id)
    if target is None:
        return RedirectResponse("/campaigns", status_code=303)

    # Memory / UX check: don't offer a second draft while one is active.
    # The partial unique index (one_active_draft_per_target) is the
    # authoritative guard behind this — add_draft below still enforces it
    # even if two requests race past this check at the same time.
    if db.get_active_draft_for_target(workspace_id, target_id) is not None:
        return RedirectResponse("/approvals", status_code=303)

    campaign = db.get_campaign(workspace_id, target["campaign_id"])
    if campaign is None:
        return RedirectResponse("/campaigns", status_code=303)
    brief = Brief.model_validate_json(campaign["brief_json"])

    settings = db.get_settings(workspace_id)
    result = drafting.draft_outreach(brief, dict(target), settings)

    try:
        db.add_draft(
            workspace_id, target_id, result.body, result.model_used, result.status, result.reason
        )
    except db.ActiveDraftExists:
        # Lost the race against a concurrent draft request; the winner's
        # draft is already in the queue.
        return RedirectResponse("/approvals", status_code=303)
    except db.NotFound:
        return RedirectResponse("/campaigns", status_code=303)

    return RedirectResponse("/approvals", status_code=303)


@app.get("/approvals")
def approvals_list(
    request: Request,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    drafts = [
        {**dict(d), "fit_class": _fit_class(d["target_fit_score"])}
        for d in db.list_pending_drafts(workspace["id"])
    ]
    return templates.TemplateResponse(
        request, "approvals.html", {**nav_context(workspace), "drafts": drafts}
    )


@app.post("/drafts/{draft_id}/action")
def draft_action(
    draft_id: int,
    action: DraftAction = Form(...),
    body: str = Form(...),
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)
    workspace_id = workspace["id"]

    try:
        if action == "save":
            db.save_draft_body(workspace_id, draft_id, body)
        elif action == "approve":
            db.approve_draft(workspace_id, draft_id, body)
        else:
            db.reject_draft(workspace_id, draft_id)
    except db.InvalidDraftBody as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except db.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except db.NotFound:
        return RedirectResponse("/approvals", status_code=303)

    return RedirectResponse("/approvals", status_code=303)


@app.get("/pipeline")
def pipeline_board(
    request: Request,
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)
    workspace_id = workspace["id"]

    columns: dict[str, list[dict]] = {stage: [] for stage in db.STAGES}
    for t in db.list_pipeline_targets(workspace_id):
        stage = t["stage"]
        columns[stage].append(
            {
                **dict(t),
                "fit_class": _fit_class(t["target_fit_score"]),
                # Ordered per STAGES so a "forward" move always renders
                # before "Decline" — never derived from dict/set iteration
                # order, which Python does not guarantee to match STAGES.
                "next_stages": sorted(db.STAGE_TRANSITIONS[stage], key=db.STAGES.index),
            }
        )

    return templates.TemplateResponse(
        request, "pipeline.html", {**nav_context(workspace), "columns": columns}
    )


@app.post("/targets/{target_id}/stage")
def update_target_stage(
    target_id: int,
    stage: PipelineStage = Form(...),
    workspace=Depends(get_current_workspace),
):
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)
    workspace_id = workspace["id"]

    try:
        db.set_target_stage(workspace_id, target_id, stage)
    except db.NotFound:
        # Covers both "no such target in this workspace" and "target has no
        # approved draft yet" — the two are deliberately indistinguishable.
        return RedirectResponse("/pipeline", status_code=303)
    except db.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return RedirectResponse("/pipeline", status_code=303)
