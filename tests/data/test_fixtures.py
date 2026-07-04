"""Fixtures pipeline tests: parse (pure, from a recorded payload) + ingest + lookup."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.data.fixtures import (
    FixtureRow,
    ingest_fixtures,
    parse_fixtures,
    season_code,
    upcoming_fixtures,
)
from bundespredict.data.models import Fixture, Team
from bundespredict.data.team_aliases import UnmappedTeamError

SAMPLE = Path(__file__).parent / "fixtures" / "openligadb_sample.json"


def _sample_payload() -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return payload


def test_season_code() -> None:
    assert season_code(2026) == "2627"
    assert season_code(2099) == "9900"


def test_parse_recorded_payload() -> None:
    rows = parse_fixtures(_sample_payload(), 2026)
    assert len(rows) == 3
    bayern = next(r for r in rows if r.home == "FC Bayern München")
    assert bayern.away == "VfB Stuttgart"
    assert bayern.season == "2627"
    assert bayern.matchday == 1
    # UTC, naive, with the Z suffix stripped correctly.
    assert bayern.kickoff_utc == datetime(2026, 8, 28, 18, 30)


def test_parse_skips_finished_and_incomplete_entries() -> None:
    payload = _sample_payload()
    payload[0]["matchIsFinished"] = True
    payload[1]["matchDateTimeUTC"] = None
    rows = parse_fixtures(payload, 2026)
    assert len(rows) == 1
    assert rows[0].home == "Borussia Dortmund"


def test_ingest_creates_teams_and_mirrors_the_schedule(session: Session) -> None:
    rows = parse_fixtures(_sample_payload(), 2026)
    stored = ingest_fixtures(session, rows)
    assert stored == 3

    # A club with no result history (fresh promotion) got a canonical teams row.
    hsv = session.execute(select(Team).where(Team.name == "Hamburger SV")).scalar_one()
    assert hsv.id is not None
    # OpenLigaDB's spelling resolved to the existing canonical name convention.
    assert session.execute(select(Team.id).where(Team.name == "Bayern Munich")).scalar_one()

    # Replace semantics: re-ingest with a rescheduled kickoff updates, no duplicates.
    moved = [
        FixtureRow(
            season=r.season,
            matchday=r.matchday,
            kickoff_utc=r.kickoff_utc.replace(hour=17),
            home=r.home,
            away=r.away,
        )
        for r in rows
    ]
    assert ingest_fixtures(session, moved) == 3
    kickoffs = session.execute(select(Fixture.kickoff_utc)).scalars().all()
    assert len(kickoffs) == 3
    assert all(k.hour == 17 for k in kickoffs)


def test_ingest_rejects_unmapped_names_before_writing(session: Session) -> None:
    rows = [
        FixtureRow(
            season="2627",
            matchday=1,
            kickoff_utc=datetime(2026, 8, 29, 13, 30),
            home="Nonexistent FC",
            away="Borussia Dortmund",
        )
    ]
    with pytest.raises(UnmappedTeamError):
        ingest_fixtures(session, rows)
    assert session.execute(select(Fixture)).first() is None


def test_upcoming_fixtures_filters_and_orders(session: Session) -> None:
    ingest_fixtures(session, parse_fixtures(_sample_payload(), 2026))

    all_from_july = upcoming_fixtures(session, on_or_after=date(2026, 7, 1))
    assert len(all_from_july) == 3
    # Soonest first: the Friday-evening opener.
    assert all_from_july[0].home == "Bayern Munich"

    dortmund = upcoming_fixtures(session, team="Borussia Dortmund", on_or_after=date(2026, 7, 1))
    assert len(dortmund) == 1
    assert dortmund[0].away == "Hamburger SV"
    assert dortmund[0].matchday == 1

    # A cutoff after every kickoff yields nothing.
    assert upcoming_fixtures(session, on_or_after=date(2026, 9, 1)) == ()


def test_upcoming_fixtures_unknown_team_raises(session: Session) -> None:
    ingest_fixtures(session, parse_fixtures(_sample_payload(), 2026))
    with pytest.raises(ValueError, match="unknown team"):
        upcoming_fixtures(session, team="Made Up FC", on_or_after=date(2026, 7, 1))
