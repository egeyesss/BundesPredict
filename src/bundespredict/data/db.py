"""Database engine and session plumbing.

The model engine stays pure (no DB); this module is the only place that knows
how to reach Postgres. ``DATABASE_URL`` is read from the environment so the same
code works in compose (``@db:5432``) and locally (``@localhost:5433``).
"""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

# Local default matches the compose host-port mapping (5432 collides with a
# local Postgres, so compose publishes 5433).
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://bundespredict:bundespredict@localhost:5433/bundespredict"
)


def _normalize(url: str) -> str:
    """Pin a bare ``postgresql://`` URL to the psycopg (v3) driver.

    compose and most hosting providers hand out driverless URLs, and SQLAlchemy
    defaults those to psycopg2, which isn't installed here.
    """
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def get_database_url() -> str:
    """Return the configured database URL, normalized to the psycopg3 driver."""
    return _normalize(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def make_engine(url: str | None = None) -> Engine:
    # Normalize here too: callers may pass a URL from their own config (the API's
    # pydantic settings) that never went through get_database_url.
    return create_engine(_normalize(url) if url else get_database_url())


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
