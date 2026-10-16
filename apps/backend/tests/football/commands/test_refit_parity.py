"""The Django `ingest_results` + `refit` path must land the same database state as the
legacy SQLAlchemy path (`ingest_dir` + `scripts/refit.py`) on the same CSV snapshot."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine
from testcontainers.community.postgres import PostgresContainer

from bundespredict.data.db import make_session_factory
from bundespredict.data.ingest import ingest_dir
from bundespredict.data.models import Base
from football.models import Match, ModelRun, TeamParam

pytestmark = pytest.mark.django_db

CSV_DIR = Path(__file__).resolve().parent / "results_csv"
REPO_ROOT = Path(__file__).resolve().parents[5]
LEGACY_DATABASE = "legacy_parity"
TOLERANCE = 1e-9


@pytest.fixture
def legacy_database_url(postgres_container: PostgresContainer) -> Iterator[str]:
    """A second, empty database on the same Postgres, shaped by the legacy SQLAlchemy models."""
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    user, password = postgres_container.username, postgres_container.password
    with psycopg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=postgres_container.dbname,
        autocommit=True,
    ) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {LEGACY_DATABASE}")
        admin.execute(f"CREATE DATABASE {LEGACY_DATABASE}")
    url = f"postgresql://{user}:{password}@{host}:{port}/{LEGACY_DATABASE}"
    engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    Base.metadata.create_all(engine)
    engine.dispose()
    yield url


def run_legacy_pipeline(database_url: str) -> None:
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    with make_session_factory(engine)() as session:
        ingest_dir(session, CSV_DIR)
    engine.dispose()
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "refit.py"), "--skip-download"],
        check=True,
        cwd=REPO_ROOT,
        # Django pins the process to UTC; the script reads the local date, so pin it here too.
        env={**os.environ, "DATABASE_URL": database_url, "TZ": "UTC"},
    )


def legacy_rows(database_url: str, query: str) -> list[tuple[object, ...]]:
    with psycopg.connect(database_url) as conn:
        return [tuple(row) for row in conn.execute(query).fetchall()]


def test_django_pipeline_matches_the_legacy_pipeline(
    legacy_database_url: str, run_command: Callable[..., str]
) -> None:
    run_legacy_pipeline(legacy_database_url)

    run_command("ingest_results", raw_dir=str(CSV_DIR))
    run_command("refit", skip_download=True)

    legacy_matches = legacy_rows(
        legacy_database_url,
        "SELECT m.season, h.name, a.name, m.date, m.home_goals, m.away_goals, m.ftr, "
        "m.b365_home, m.avgc_away FROM matches m JOIN teams h ON h.id = m.home_id "
        "JOIN teams a ON a.id = m.away_id ORDER BY m.season, h.name, a.name",
    )
    django_matches = [
        (
            m.season,
            m.home.name,
            m.away.name,
            m.date,
            m.home_goals,
            m.away_goals,
            m.ftr,
            m.b365_home,
            m.avgc_away,
        )
        for m in Match.objects.select_related("home", "away").order_by(
            "season", "home__name", "away__name"
        )
    ]
    assert len(django_matches) == 90
    assert django_matches == legacy_matches

    legacy_run = legacy_rows(
        legacy_database_url,
        "SELECT model_type, as_of_date, xi, rho, home_adv, xg_coef, log_likelihood, n_matches, "
        "version, notes FROM model_runs",
    )
    django_run = ModelRun.objects.get()
    assert len(legacy_run) == 1
    (
        model_type,
        as_of_date,
        xi,
        rho,
        home_adv,
        xg_coef,
        log_likelihood,
        n_matches,
        version,
        notes,
    ) = legacy_run[0]
    assert (django_run.model_type, django_run.as_of_date) == (model_type, as_of_date)
    assert (django_run.n_matches, django_run.version, django_run.notes) == (
        n_matches,
        version,
        notes,
    )
    for django_value, legacy_value in (
        (django_run.xi, xi),
        (django_run.rho, rho),
        (django_run.home_adv, home_adv),
        (django_run.xg_coef, xg_coef),
        (django_run.log_likelihood, log_likelihood),
    ):
        assert django_value == pytest.approx(legacy_value, abs=TOLERANCE, rel=0)

    legacy_params = legacy_rows(
        legacy_database_url,
        "SELECT t.name, p.attack, p.defense FROM team_params p JOIN teams t ON t.id = p.team_id "
        "ORDER BY t.name",
    )
    django_params = [
        (p.team.name, p.attack, p.defense)
        for p in TeamParam.objects.select_related("team").order_by("team__name")
    ]
    assert [name for name, _, _ in django_params] == [name for name, _, _ in legacy_params]
    for (_, attack, defense), (_, legacy_attack, legacy_defense) in zip(
        django_params, legacy_params, strict=True
    ):
        assert attack == pytest.approx(legacy_attack, abs=TOLERANCE, rel=0)
        assert defense == pytest.approx(legacy_defense, abs=TOLERANCE, rel=0)
