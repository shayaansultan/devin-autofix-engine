"""Process-wide shared httpx.AsyncClient.

Reusing one client (and its connection pool) across all Devin + GitHub calls is
cheaper than opening a new client per request. Lifecycle is owned by the FastAPI
app (closed on shutdown via `close_client`).
"""
from __future__ import annotations

import httpx

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared async HTTP client, creating it lazily."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30)
    return _client


async def close_client() -> None:
    """Close the shared client (called on app shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None
