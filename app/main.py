"""Outpost FastAPI application.

Slice 0: a runnable app with SQLite connected, a health route, and a styled
empty shell honoring the design.md tokens with a light/dark theme toggle.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create/connect the database on startup so a fresh checkout just works.
    db.init()
    yield


app = FastAPI(title="Outpost", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """The styled empty shell."""
    return templates.TemplateResponse(request, "index.html")
