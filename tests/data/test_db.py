"""Engine-level tests for surviving a connection the server has closed.

Managed Postgres drops connections that have been idle too long. The pool keeps
handing them out anyway unless it checks first, which is how a quiet API started
returning 500 on the first request after a lull. These tests kill a pooled
connection the way a provider's idle timeout would and check what happens next.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from bundespredict.data.db import make_engine


def _url(engine: Engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def _checkout_then_kill(engine: Engine, killer: Engine) -> None:
    """Open a connection, return it to the pool, then terminate it server-side."""
    with engine.connect() as conn:
        pid = conn.execute(text("SELECT pg_backend_pid()")).scalar_one()

    with killer.connect() as conn:
        conn.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
        # Termination is a signal, so the backend takes a moment to actually go.
        # Poll rather than sleep a fixed amount, or the test races on a slow box.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            alive = conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE pid = :pid"),
                {"pid": pid},
            ).scalar_one()
            if alive == 0:
                return
            time.sleep(0.05)
    raise AssertionError(f"backend {pid} did not terminate")


def test_pool_replaces_a_connection_the_server_closed(pg_engine: Engine) -> None:
    engine = make_engine(_url(pg_engine))
    try:
        _checkout_then_kill(engine, pg_engine)
        # The pool still holds the dead connection; the pre-ping should notice
        # and swap in a fresh one instead of raising.
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_without_pre_ping_the_dead_connection_is_handed_out(pg_engine: Engine) -> None:
    """The failure make_engine exists to prevent, so the fix can't be quietly dropped."""
    engine = create_engine(_url(pg_engine))
    try:
        _checkout_then_kill(engine, pg_engine)
        with pytest.raises(OperationalError):
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()
