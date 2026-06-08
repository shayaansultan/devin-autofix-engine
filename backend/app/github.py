"""GitHub REST client: read issues, comment, read PR / CI state."""
from __future__ import annotations

import logging
from typing import Any

from .config import get_settings
from .http import get_client

logger = logging.getLogger(__name__)

API = "https://api.github.com"


class GithubClient:
    def __init__(self) -> None:
        self._token = get_settings().github_token
        self._headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    async def get_issue(self, repo: str, number: int) -> dict[str, Any]:
        resp = await get_client().get(
            f"{API}/repos/{repo}/issues/{number}", headers=self._headers
        )
        resp.raise_for_status()
        return resp.json()

    async def comment_on_issue(self, repo: str, number: int, body: str) -> None:
        if not self._token:
            return  # commenting is best-effort; skip silently if no token
        resp = await get_client().post(
            f"{API}/repos/{repo}/issues/{number}/comments",
            headers=self._headers,
            json={"body": body},
        )
        # don't raise: a failed comment shouldn't break the pipeline
        if resp.status_code >= 400:
            logger.warning(
                "comment on %s#%s failed (%s): %s",
                repo,
                number,
                resp.status_code,
                resp.text[:200],
            )

    async def get_pr_created_at(self, repo: str, pr_url: str) -> float | None:
        """Return the PR's creation time (epoch seconds), or None.

        This is an immutable GitHub timestamp, so using it to derive time-to-PR
        keeps the metric stable across rehydration (unlike local bookkeeping
        recreated after the PR already exists).
        """
        try:
            number = int(pr_url.rstrip("/").split("/")[-1])
        except ValueError:
            return None
        url = f"{API}/repos/{repo}/pulls/{number}"
        resp = await get_client().get(url, headers=self._headers)
        # A stale/invalid token shouldn't break a public-repo read: retry
        # unauthenticated on an auth error.
        if resp.status_code in (401, 403) and "Authorization" in self._headers:
            anon = {k: v for k, v in self._headers.items() if k != "Authorization"}
            resp = await get_client().get(url, headers=anon)
        if resp.status_code >= 400:
            return None
        created = resp.json().get("created_at")
        if not created:
            return None
        from datetime import datetime

        try:
            return datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None

    async def get_pr_ci_status(self, repo: str, pr_url: str) -> str | None:
        """Return 'success' | 'failure' | 'pending' | None for a PR's head commit."""
        # pr_url like https://github.com/owner/repo/pull/7
        try:
            number = int(pr_url.rstrip("/").split("/")[-1])
        except ValueError:
            return None
        client = get_client()
        pr = await client.get(f"{API}/repos/{repo}/pulls/{number}", headers=self._headers)
        if pr.status_code >= 400:
            return None
        sha = pr.json().get("head", {}).get("sha")
        if not sha:
            return None
        # check-runs (GitHub Actions etc.)
        runs = await client.get(
            f"{API}/repos/{repo}/commits/{sha}/check-runs", headers=self._headers
        )
        if runs.status_code >= 400:
            return None
        check_runs = runs.json().get("check_runs", [])
        if not check_runs:
            return None
        conclusions = [c.get("conclusion") for c in check_runs]
        if any(c is None for c in conclusions):
            return "pending"
        if all(c in ("success", "skipped", "neutral") for c in conclusions):
            return "success"
        return "failure"
