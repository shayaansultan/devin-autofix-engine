"""FastAPI app: GitHub webhook trigger + manual trigger + dashboard API + static UI."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .devin import DevinClient
from .http import close_client
from .poller import poll_loop
from .service import rehydrate_from_devin, trigger_issue
from .store import store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Recover prior runs from Devin session tags (near-stateless design).
    if get_settings().rehydrate_on_startup:
        try:
            await rehydrate_from_devin()
        except Exception as exc:  # noqa: BLE001
            logger.warning("startup rehydrate skipped: %s", exc)
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    await close_client()


app = FastAPI(title="Devin Autofix Engine", lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Health + config
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "repo": s.github_repo,
        "trigger_label": s.trigger_label,
        "devin_configured": bool(s.devin_api_token and s.devin_org_id),
        "github_configured": bool(s.github_token),
    }


@app.get("/api/config")
async def config() -> dict:
    s = get_settings()
    return {"repo": s.github_repo, "trigger_label": s.trigger_label}


# --------------------------------------------------------------------------- #
# Dashboard read API
# --------------------------------------------------------------------------- #
@app.get("/api/runs")
async def list_runs() -> dict:
    return {"runs": [r.to_dict() for r in store.all()]}


@app.get("/api/stats")
async def stats() -> dict:
    return store.stats()


@app.get("/api/runs/{repo_owner}/{repo_name}/{issue_number}")
async def run_detail(repo_owner: str, repo_name: str, issue_number: int) -> dict:
    run = store.get(f"{repo_owner}/{repo_name}", issue_number)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run.to_dict()


@app.get("/api/runs/{repo_owner}/{repo_name}/{issue_number}/messages")
async def run_messages(repo_owner: str, repo_name: str, issue_number: int) -> dict:
    """Live activity log for a run: the Devin session's chronological messages."""
    run = store.get(f"{repo_owner}/{repo_name}", issue_number)
    if not run or not run.session_id:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        messages = await DevinClient().get_session_messages(run.session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch messages for %s failed: %s", run.session_id, exc)
        messages = []
    return {"messages": messages}


# --------------------------------------------------------------------------- #
# Triggers
# --------------------------------------------------------------------------- #
@app.post("/api/trigger")
async def manual_trigger(payload: dict) -> dict:
    """Manual trigger (dashboard button / demo safety net): {"issue_number": N}."""
    s = get_settings()
    issue_number = payload.get("issue_number")
    repo = payload.get("repo", s.github_repo)
    if not issue_number:
        raise HTTPException(status_code=400, detail="issue_number required")
    run = await trigger_issue(
        repo, int(issue_number), trigger_type="manual", triggered_by="dashboard"
    )
    return run.to_dict()


def _parse_webhook_payload(body: bytes, content_type: str) -> dict:
    """Parse a GitHub webhook body. GitHub sends either raw JSON or a url-encoded
    form with the JSON under a `payload` field, depending on the hook's
    content-type setting -- accept both so the trigger works either way."""
    if content_type.startswith("application/x-www-form-urlencoded"):
        raw = (parse_qs(body.decode("utf-8")).get("payload") or ["{}"])[0]
    else:
        raw = body.decode("utf-8") or "{}"
    return json.loads(raw)


def _verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret:
        return True  # no secret configured -> skip verification (dev mode)
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/api/webhook/github")
async def github_webhook(request: Request) -> JSONResponse:
    """GitHub webhook. Fires a session when a human applies the trigger label."""
    s = get_settings()
    body = await request.body()
    if not _verify_signature(
        s.github_webhook_secret, body, request.headers.get("X-Hub-Signature-256")
    ):
        raise HTTPException(status_code=401, detail="invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = _parse_webhook_payload(body, request.headers.get("Content-Type", ""))

    if event != "issues" or payload.get("action") != "labeled":
        return JSONResponse({"ignored": True, "reason": f"event={event}"})

    label = (payload.get("label") or {}).get("name", "")
    if label != s.trigger_label:
        return JSONResponse({"ignored": True, "reason": f"label={label}"})

    issue = payload["issue"]
    repo = payload["repository"]["full_name"]
    sender = (payload.get("sender") or {}).get("login", "unknown")

    run = await trigger_issue(
        repo, issue["number"], trigger_type="webhook", triggered_by=sender
    )
    return JSONResponse({"triggered": True, "session_url": run.session_url})


# --------------------------------------------------------------------------- #
# Static frontend (built React app), mounted last so /api/* takes precedence
# --------------------------------------------------------------------------- #
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
