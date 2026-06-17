"""FastAPI dependencies: a DB session and the LLM client.

Both are dependencies so tests can override them — a throwaway Postgres session
and a scripted client — and exercise the endpoint with no network and no API
key. The session factory and the client are cached at the app level; building an
Anthropic client per request would be wasteful and a new engine per request
would leak connections.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import cast

import anthropic
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from bundespredict.agent.loop import LLMClient
from bundespredict.data.db import get_database_url, make_engine, make_session_factory

from .config import get_settings


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    engine = make_engine(settings.database_url or get_database_url())
    return make_session_factory(engine)


def get_session() -> Iterator[Session]:
    """Yield a request-scoped session; closed when the request finishes."""
    with _session_factory()() as session:
        yield session


@lru_cache
def _cached_client(api_key: str) -> LLMClient:
    # The real client satisfies the loop's minimal LLMClient surface at runtime;
    # its precise overloaded type doesn't structurally match, so cast.
    return cast(LLMClient, anthropic.Anthropic(api_key=api_key))


def get_llm_client() -> LLMClient:
    """Return the Anthropic client, or 503 if no API key is configured."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="agent unavailable: ANTHROPIC_API_KEY is not configured",
        )
    return _cached_client(settings.anthropic_api_key)
