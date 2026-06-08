"""Configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read .env from either the repo root (Docker / running from root) or the
    # backend dir (local dev: `cd backend && uv run uvicorn ...`). Real env vars
    # always win, so Docker's injected env_file still takes precedence.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Devin v3 API
    devin_api_token: str = ""  # cog_... service-user token
    devin_org_id: str = ""  # org-...
    devin_api_base: str = "https://api.devin.ai"
    # Optional reusable playbook bundling repo conventions
    playbook_id: str | None = None
    # Safety cap on Agent Compute Units per session
    max_acu_limit: int | None = 25
    # Optional illustrative $ per ACU for the dashboard cost view (0 = show ACUs only).
    # Enterprise ACU rates are set per order form; set this to your real rate.
    acu_usd_rate: float = 0.0

    # ---- Demo mode (illustrative cost) -------------------------------------
    # Self-serve Devin accounts do not expose per-session ACUs through the API
    # (the field is always 0; ACU telemetry is the Enterprise path). For demos
    # on such accounts, DEMO_MODE estimates ACUs from each session's active
    # runtime so the cost view is populated. Real ACUs always take precedence
    # when the API reports them, so this is a no-op on Enterprise orgs.
    demo_mode: bool = False
    # ACUs per active minute. Cognition's published rule of thumb is that ~15
    # minutes of active Devin work ≈ 1 ACU, i.e. ~0.0667 ACU/min.
    acu_per_minute: float = 0.0667

    # GitHub
    github_token: str = ""
    github_repo: str = "shayaansultan/superset"  # owner/repo this engine watches
    github_webhook_secret: str = ""

    # The label a human applies to an issue to request autonomous remediation
    trigger_label: str = "devin-autofix"

    # How often the background poller refreshes live session state (seconds)
    poll_interval_seconds: int = 6

    # Rebuild the store from Devin session tags on startup (near-stateless recovery).
    # Set false to start with an empty dashboard, e.g. for a clean demo/cost run.
    rehydrate_on_startup: bool = True

    @property
    def org_sessions_url(self) -> str:
        return f"{self.devin_api_base}/v3/organizations/{self.devin_org_id}/sessions"


@lru_cache
def get_settings() -> Settings:
    return Settings()
