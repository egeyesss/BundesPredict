"""Tests for Understat xG parsing and backfill onto matches.

The parser runs against a committed slice of real ``datesData`` (pinning the
payload shape); the ingest test uses the shared Postgres session and checks the
xG lands on the right fixture, that unplayed rows are dropped, and that a row
without a matching fixture is counted rather than inserted.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from bundespredict.data.models import Match, Team
from bundespredict.data.team_aliases import UnmappedTeamError
from bundespredict.data.understat import (
    ingest_understat,
    parse_understat_season,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "understat_sample.json"


def _payload() -> list[dict[str, Any]]:
    return list(json.loads(_FIXTURE.read_text()))


def test_parse_drops_unplayed_and_canonicalizes() -> None:
    rows = parse_understat_season(_payload(), "2324")
    # Two played matches; the unplayed (isResult false) row is dropped.
    assert len(rows) == 2
    first = rows[0]
    assert first.home == "SV Werder Bremen"  # canonicalized from "Werder Bremen"
    assert first.away == "Bayern Munich"
    assert first.home_xg == 0.63974
    assert first.away_xg == 2.89704
    assert first.date == date(2023, 8, 18)


def test_parse_raises_on_unmapped_team() -> None:
    payload = [
        {
            "id": "9",
            "isResult": True,
            "h": {"title": "Some New Club"},
            "a": {"title": "Bayern Munich"},
            "goals": {"h": "1", "a": "1"},
            "xG": {"h": "1.0", "a": "1.0"},
            "datetime": "2023-08-18 18:30:00",
        }
    ]
    try:
        parse_understat_season(payload, "2324")
    except UnmappedTeamError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected UnmappedTeamError")


def _seed_fixture(session: Session) -> None:
    bremen = Team(name="SV Werder Bremen")
    bayern = Team(name="Bayern Munich")
    session.add_all([bremen, bayern])
    session.flush()
    session.add(
        Match(
            season="2324",
            date=date(2023, 8, 18),
            home_id=bremen.id,
            away_id=bayern.id,
            home_goals=0,
            away_goals=4,
            ftr="A",
        )
    )
    session.commit()


def test_ingest_backfills_xg_onto_the_matching_fixture(session: Session) -> None:
    _seed_fixture(session)
    # Only the Bremen-Bayern fixture exists; the Augsburg-Gladbach row has no
    # matching match and must be counted as unmatched, not inserted.
    rows = parse_understat_season(_payload(), "2324")
    stats = ingest_understat(session, {"2324": rows})
    assert stats.matched == 1
    assert stats.unmatched == 1

    match = session.query(Match).filter_by(season="2324").one()
    assert match.home_xg == 0.63974
    assert match.away_xg == 2.89704
    # No new match rows were created for the unmatched Understat row.
    assert session.query(Match).count() == 1


def test_ingest_is_idempotent(session: Session) -> None:
    _seed_fixture(session)
    rows = parse_understat_season(_payload(), "2324")
    ingest_understat(session, {"2324": rows})
    ingest_understat(session, {"2324": rows})
    assert session.query(Match).count() == 1
    assert session.query(Match).one().home_xg == 0.63974
