"""Runtime configuration for the API.

Reads from the environment and an optional ``.env`` file (gitignored), so the
Anthropic key and database URL are configured the same way in compose and
locally without ever being hardcoded. Cached so the file is read once.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from bundespredict.agent.loop import DEV_MODEL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # None -> fall back to the data layer's own DATABASE_URL resolution.
    database_url: str | None = None
    anthropic_api_key: str | None = None
    # Haiku by default (cheap); override to the prod model via AGENT_MODEL.
    agent_model: str = DEV_MODEL
    # The browser origin allowed by CORS; set to the deployed web URL in prod.
    web_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
