"""Postgres-backed fixtures for data-layer tests.

A real Postgres (via testcontainers) is spun up once per test session so the
ingest path exercises actual ``ON CONFLICT`` upsert semantics, not a SQLite
approximation. Each test gets a clean schema (tables truncated between tests).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

# Skip testcontainers' Ryuk reaper container: the fixture's context manager
# already stops the Postgres container, and pulling Ryuk needs Docker Hub access
# that sandboxed/offline environments may not have.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest  # noqa: E402
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.models import Base


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        engine = make_engine(postgres.get_connection_url())
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def session(pg_engine: Engine) -> Iterator[Session]:
    factory = make_session_factory(pg_engine)
    with factory() as sess:
        yield sess
    # Reset state between tests; RESTART IDENTITY keeps row counts deterministic.
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE matches, team_aliases, teams RESTART IDENTITY CASCADE"))
