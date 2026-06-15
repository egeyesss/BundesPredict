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


def get_database_url() -> str:
    """Return the configured database URL, normalized to the psycopg3 driver."""
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    # compose sets a bare postgresql:// URL; pin it to the psycopg (v3) driver.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url())


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
