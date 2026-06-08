"""Thin client for the Devin v3 organization-scoped API.

Docs: https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions
"""
from __future__ import annotations

from typing import Any

from .config import get_settings
from .http import get_client


class DevinClient:
    def __init__(self) -> None:
        s = get_settings()
        self._base = s.org_sessions_url
        self._headers = {
            "Authorization": f"Bearer {s.devin_api_token}",
            "Content-Type": "application/json",
        }

    async def create_session(
        self,
        *,
        prompt: str,
        title: str,
        tags: list[str],
        repos: list[str],
        structured_output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        s = get_settings()
        body: dict[str, Any] = {
            "prompt": prompt,
            "title": title,
            "tags": tags,
            "repos": repos,
        }
        if structured_output_schema:
            body["structured_output_schema"] = structured_output_schema
        if s.playbook_id:
            body["playbook_id"] = s.playbook_id
        if s.max_acu_limit:
            body["max_acu_limit"] = s.max_acu_limit

        resp = await get_client().post(self._base, headers=self._headers, json=body)
        resp.raise_for_status()
        return resp.json()

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Get full session state (status, status_detail, structured_output, PRs, ACUs)."""
        resp = await get_client().get(f"{self._base}/{session_id}", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def get_session_messages(
        self, session_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List a session's chronological messages (the live activity log).

        Each item: {event_id, source ("devin"|"user"), message, created_at}.
        """
        resp = await get_client().get(
            f"{self._base}/{session_id}/messages",
            headers=self._headers,
            params={"limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("items") or []
        return data

    async def list_sessions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """List org sessions (used to rehydrate state on startup)."""
        resp = await get_client().get(
            self._base, headers=self._headers, params={"limit": limit}
        )
        resp.raise_for_status()
        data = resp.json()
        # v3 list returns either a bare list or an object with items
        if isinstance(data, dict):
            return data.get("items") or data.get("sessions") or []
        return data
