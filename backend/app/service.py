"""Orchestration: turn a labeled issue into a managed Devin session."""
from __future__ import annotations

import logging
import time

from .config import get_settings
from .devin import DevinClient
from .github import GithubClient
from .prompts import STRUCTURED_OUTPUT_SCHEMA, build_prompt
from .store import ENGINE_TAG, Run, store

logger = logging.getLogger(__name__)

# Map GitHub issue labels -> our coarse category buckets (for the dashboard).
_LABEL_TO_CATEGORY = {
    "security": "security",
    "vulnerability": "security",
    "dependencies": "dependency",
    "dependency": "dependency",
    "deprecation": "deprecation",
    "tests": "tests",
    "test": "tests",
    "documentation": "documentation",
    "docs": "documentation",
    "code-quality": "code_quality",
    "refactor": "code_quality",
}


def _category_from_labels(labels: list[str]) -> str:
    for label in labels:
        cat = _LABEL_TO_CATEGORY.get(label.lower())
        if cat:
            return cat
    return "other"


def _tag_value(tags: list[str], prefix: str) -> str | None:
    for t in tags:
        if t.startswith(prefix):
            return t[len(prefix):]
    return None


def _to_epoch(val: object) -> float | None:
    """Coerce a Devin timestamp (epoch int/float or ISO-8601 string) to seconds."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str) and val:
        from datetime import datetime

        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


async def refresh_run(
    client: DevinClient, run: Run, *, track_timing: bool = True
) -> None:
    """Pull the latest session state for a run into the store (used by poller + rehydrate).

    `track_timing=False` (rehydrate) avoids stamping a fake time-to-PR on runs
    whose PR predates this process.
    """
    try:
        session = await client.get_session(run.session_id)
    except Exception as exc:  # noqa: BLE001 - must stay alive
        logger.warning("refresh get_session %s failed: %s", run.session_id, exc)
        return

    run.status = session.get("status", run.status)
    run.status_detail = session.get("status_detail")
    run.devin_category = session.get("category")
    run.subcategory = session.get("subcategory")
    run.acus_consumed = session.get("acus_consumed", run.acus_consumed) or 0.0
    run.session_created_at = _to_epoch(session.get("created_at")) or run.session_created_at
    run.session_updated_at = _to_epoch(session.get("updated_at")) or run.session_updated_at
    so = session.get("structured_output")
    if so:
        run.structured_output = so

    prs = session.get("pull_requests") or []
    if prs:
        pr = prs[0]
        pr_url = pr.get("pr_url") or pr.get("url")
        if pr_url:
            if not run.pr_url and track_timing:
                run.pr_first_seen_at = run.pr_first_seen_at or time.time()
            run.pr_url = pr_url
            run.pr_state = pr.get("pr_state") or pr.get("state")

    if run.structured_output and run.structured_output.get("pr_url") and not run.pr_url:
        run.pr_url = run.structured_output["pr_url"]
        if track_timing:
            run.pr_first_seen_at = run.pr_first_seen_at or time.time()

    if run.pr_url:
        gh = GithubClient()
        ci = await gh.get_pr_ci_status(run.repo, run.pr_url)
        if ci:
            run.ci_status = ci
        # Capture the PR's immutable creation time once, so time-to-PR (and the
        # ACU estimate derived from it) is stable for rehydrated runs.
        if not run.pr_created_at:
            created = await gh.get_pr_created_at(run.repo, run.pr_url)
            if created:
                run.pr_created_at = created

    run.updated_at = time.time()
    store.upsert(run)


async def rehydrate_from_devin() -> int:
    """Rebuild the in-memory store from Devin sessions tagged by this engine.

    Demonstrates the near-stateless design: on restart we recover all runs from
    Devin's own session metadata (tags + structured_output + pull_requests),
    no database required.
    """
    client = DevinClient()
    github = GithubClient()
    try:
        sessions = await client.list_sessions(limit=100)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rehydrate list_sessions failed: %s", exc)
        return 0

    count = 0
    for s in sessions:
        tags = s.get("tags") or []
        if ENGINE_TAG not in tags:
            continue
        issue_raw = _tag_value(tags, "issue:")
        repo_slug = _tag_value(tags, "repo:")
        if not issue_raw:
            continue
        try:
            issue_number = int(issue_raw)
        except ValueError:
            continue
        repo = get_settings().github_repo
        run = store.get(repo, issue_number) or Run(repo=repo, issue_number=issue_number)
        run.session_id = s.get("session_id", run.session_id)
        run.session_url = s.get("url", run.session_url)
        run.status = s.get("status", run.status)
        run.issue_category = _tag_value(tags, "category:") or run.issue_category
        run.issue_url = f"https://github.com/{repo}/issues/{issue_number}"
        run.triggered_by = s.get("user_id") or run.triggered_by

        # Clean issue title + category from GitHub (best-effort)
        try:
            issue = await github.get_issue(repo, issue_number)
            run.issue_title = issue.get("title") or run.issue_title
            labels = [l["name"] for l in issue.get("labels", []) if isinstance(l, dict)]
            cat = _category_from_labels(labels)
            if cat != "other":
                run.issue_category = cat
        except Exception:  # noqa: BLE001
            if s.get("title"):
                run.issue_title = run.issue_title or s["title"]

        store.upsert(run)
        # Full enrichment: PR, structured output, ACUs, status detail.
        # track_timing=False so a pre-existing PR doesn't get a fake time-to-PR.
        await refresh_run(client, run, track_timing=False)
        count += 1
    logger.info("rehydrate recovered %s run(s) from Devin session tags", count)
    return count


async def trigger_issue(
    repo: str,
    issue_number: int,
    *,
    trigger_type: str = "manual",
    triggered_by: str = "system",
) -> Run:
    """Idempotently start (or return existing) a remediation run for an issue."""
    settings = get_settings()

    existing = store.get(repo, issue_number)
    if existing and existing.session_id:
        return existing  # dedupe: a session already exists for this issue

    github = GithubClient()
    issue = await github.get_issue(repo, issue_number)
    title = issue.get("title", f"Issue #{issue_number}")
    body = issue.get("body", "") or ""
    labels = [lbl["name"] for lbl in issue.get("labels", []) if isinstance(lbl, dict)]
    category = _category_from_labels(labels)

    run = Run(
        repo=repo,
        issue_number=issue_number,
        issue_title=title,
        issue_url=issue.get("html_url", f"https://github.com/{repo}/issues/{issue_number}"),
        issue_category=category,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
    )
    store.upsert(run)

    prompt = build_prompt(repo, issue_number, title, body)
    repo_slug = repo.split("/")[-1]
    tags = [ENGINE_TAG, f"repo:{repo_slug}", f"issue:{issue_number}", f"category:{category}"]

    client = DevinClient()
    session = await client.create_session(
        prompt=prompt,
        title=f"[{ENGINE_TAG}] Resolve issue #{issue_number}: {title[:60]}",
        tags=tags,
        repos=[repo],
        structured_output_schema=STRUCTURED_OUTPUT_SCHEMA,
    )

    run.session_id = session.get("session_id", "")
    run.session_url = session.get("url", "")
    run.status = session.get("status", "new")
    store.upsert(run)

    # Post the session link back on the issue so humans have a live trail.
    await github.comment_on_issue(
        repo,
        issue_number,
        f"🤖 **Devin Autofix** picked up this issue (trigger: `{trigger_type}`).\n\n"
        f"Tracking session: {run.session_url}\n\n"
        f"A pull request will be opened automatically once the fix is verified.",
    )
    return run
