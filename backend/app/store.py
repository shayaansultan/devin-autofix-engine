"""In-memory run store + derived KPI computation.

We deliberately avoid a database: Devin (session tags + structured_output +
pull_requests) and GitHub (PR/CI state) are the source of truth. This process
holds a lightweight cache of the runs it has triggered, refreshed by the poller,
and can rehydrate from the Devin API on restart by listing sessions by tag.
"""
from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import get_settings

ENGINE_TAG = "devin-autofix"


def _now() -> float:
    return time.time()


@dataclass
class Run:
    # identity / trigger context
    repo: str
    issue_number: int
    issue_title: str = ""
    issue_url: str = ""
    issue_category: str = "other"  # derived from issue labels
    trigger_type: str = "manual"  # "webhook" | "manual"
    triggered_by: str = "system"
    triggered_at: float = field(default_factory=_now)

    # Devin session
    session_id: str = ""
    session_url: str = ""
    status: str = "new"  # new|claimed|running|exit|error|suspended|resuming
    status_detail: str | None = None  # working|waiting_for_user|finished|...
    devin_category: str | None = None
    subcategory: str | None = None
    acus_consumed: float = 0.0
    # Devin session start (epoch seconds), recovered on rehydrate. Used with the
    # PR's creation time to derive a stable time-to-PR for rehydrated runs.
    session_created_at: float | None = None

    # results
    pr_url: str | None = None
    pr_state: str | None = None  # open|merged|closed
    ci_status: str | None = None  # success|failure|pending
    structured_output: dict[str, Any] | None = None

    # bookkeeping
    pr_first_seen_at: float | None = None
    # Immutable GitHub PR creation time (epoch seconds). Used to derive a stable
    # time-to-PR for runs rehydrated from Devin (where local trigger timing is
    # gone), instead of relying on local bookkeeping that the PR predates.
    pr_created_at: float | None = None
    updated_at: float = field(default_factory=_now)

    # ---- derived helpers -------------------------------------------------
    @property
    def is_active(self) -> bool:
        return self.status in ("new", "claimed", "running", "resuming")

    @property
    def has_pr(self) -> bool:
        return bool(self.pr_url)

    @property
    def needs_attention(self) -> bool:
        if self.status == "error":
            return True
        if self.status_detail in ("waiting_for_user", "waiting_for_approval"):
            return True
        if self.ci_status == "failure":
            return True
        return False

    @property
    def time_to_pr_seconds(self) -> float | None:
        # Fresh runs triggered on this instance have real local timing.
        if self.pr_first_seen_at:
            return self.pr_first_seen_at - self.triggered_at
        # Rehydrated runs: derive from immutable timestamps
        # (PR created_at - session created_at) so the value is stable.
        if self.pr_created_at and self.session_created_at:
            return max(0.0, self.pr_created_at - self.session_created_at)
        return None

    @property
    def estimated_human_minutes(self) -> int:
        so = self.structured_output or {}
        val = so.get("estimated_human_minutes")
        return int(val) if isinstance(val, (int, float)) else 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(
            {
                "is_active": self.is_active,
                "has_pr": self.has_pr,
                "needs_attention": self.needs_attention,
                "time_to_pr_seconds": self.time_to_pr_seconds,
            }
        )
        return d


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}  # keyed by f"{repo}#{issue_number}"
        self._lock = threading.Lock()

    @staticmethod
    def key(repo: str, issue_number: int) -> str:
        return f"{repo}#{issue_number}"

    def get(self, repo: str, issue_number: int) -> Run | None:
        return self._runs.get(self.key(repo, issue_number))

    def get_by_session(self, session_id: str) -> Run | None:
        for r in self._runs.values():
            if r.session_id == session_id:
                return r
        return None

    def upsert(self, run: Run) -> Run:
        with self._lock:
            self._runs[self.key(run.repo, run.issue_number)] = run
            return run

    def all(self) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: r.triggered_at, reverse=True)

    def active(self) -> list[Run]:
        return [r for r in self._runs.values() if r.is_active]

    # ---- KPI aggregation -------------------------------------------------
    def stats(self) -> dict[str, Any]:
        runs = list(self._runs.values())
        total = len(runs)
        active = sum(1 for r in runs if r.is_active)
        with_pr = [r for r in runs if r.has_pr]
        prs_opened = len(with_pr)
        merged = sum(1 for r in runs if r.pr_state == "merged")
        finished = [r for r in runs if not r.is_active]
        # success = a finished run that produced a PR
        successes = sum(1 for r in finished if r.has_pr)
        success_rate = (successes / len(finished) * 100) if finished else 0.0
        merge_rate = (merged / prs_opened * 100) if prs_opened else 0.0
        hours_saved = sum(r.estimated_human_minutes for r in runs if r.has_pr) / 60.0
        total_acus = sum(r.acus_consumed for r in runs)
        acus_per_pr = (total_acus / prs_opened) if prs_opened else 0.0
        ttp = [r.time_to_pr_seconds for r in with_pr if r.time_to_pr_seconds]
        avg_ttp_min = (sum(ttp) / len(ttp) / 60.0) if ttp else 0.0
        needs_attention = sum(1 for r in runs if r.needs_attention)

        # Optional $ cost view (only when an ACU rate is configured).
        rate = get_settings().acu_usd_rate
        total_cost_usd = (total_acus * rate) if rate else 0.0
        cost_per_pr_usd = (total_cost_usd / prs_opened) if (rate and prs_opened) else 0.0

        # category breakdown for the donut
        by_category: dict[str, int] = {}
        for r in runs:
            cat = _display_category(r)
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_runs": total,
            "active_sessions": active,
            "prs_opened": prs_opened,
            "prs_merged": merged,
            "success_rate": round(success_rate, 1),
            "merge_rate": round(merge_rate, 1),
            "hours_saved": round(hours_saved, 1),
            "total_acus": round(total_acus, 2),
            "acus_per_pr": round(acus_per_pr, 2),
            "acu_usd_rate": rate,
            "total_cost_usd": round(total_cost_usd, 2),
            "cost_per_pr_usd": round(cost_per_pr_usd, 2),
            "avg_time_to_pr_minutes": round(avg_ttp_min, 1),
            "needs_attention": needs_attention,
            "by_category": by_category,
        }


def _display_category(run: Run) -> str:
    """Prefer the agent's self-classified issue_type, fall back to issue label."""
    so = run.structured_output or {}
    t = so.get("issue_type")
    if isinstance(t, str) and t:
        return t
    return run.issue_category or "other"


# module-level singleton
store = RunStore()
