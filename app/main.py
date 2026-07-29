"""Outpost FastAPI application.

Slice 1: workspaces (create, switch) and per-workspace BYO-key settings.
The active workspace is tracked in a cookie; every data-touching route
depends on get_current_workspace to scope its queries.
"""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db

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
    return templates.TemplateResponse(
        request,
        "index.html",
        {"workspace": workspace, "workspaces": db.list_workspaces()},
    )


@app.get("/workspaces/new", response_class=HTMLResponse)
def new_workspace_form(
    request: Request,
    workspace=Depends(get_current_workspace),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "workspaces_new.html",
        {"workspace": workspace, "workspaces": db.list_workspaces()},
    )


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
        {
            "workspace": workspace,
            "workspaces": db.list_workspaces(),
            "setting_keys": db.SETTING_KEYS,
            "masked": masked,
        },
    )


@app.post("/settings")
def save_settings(
    workspace=Depends(get_current_workspace),
    youtube: str = Form(default=""),
    apify: str = Form(default=""),
    apollo: str = Form(default=""),
    llm: str = Form(default=""),
) -> RedirectResponse:
    if workspace is None:
        return RedirectResponse("/workspaces/new", status_code=303)

    submitted = {"youtube": youtube, "apify": apify, "apollo": apollo, "llm": llm}
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
