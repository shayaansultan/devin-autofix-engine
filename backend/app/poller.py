"""Background poller: refresh live Devin session state into the in-memory store."""
from __future__ import annotations

import asyncio
import logging

from .config import get_settings
from .devin import DevinClient
from .service import refresh_run
from .store import store

logger = logging.getLogger(__name__)


async def poll_loop() -> None:
    settings = get_settings()
    client = DevinClient()
    while True:
        try:
            # Poll active runs every cycle; also refresh PR/CI for runs whose PR
            # hasn't reached a terminal state yet.
            targets = [
                r
                for r in store.all()
                if r.session_id
                and (r.is_active or (r.pr_url and r.pr_state not in ("merged", "closed")))
            ]
            for run in targets:
                await refresh_run(client, run)
        except Exception as exc:  # noqa: BLE001
            logger.warning("poller loop error: %s", exc)
        await asyncio.sleep(settings.poll_interval_seconds)
