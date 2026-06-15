"""Postgres-backed tests for the ingestion path."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bundespredict.data.ingest import ingest_csv
from bundespredict.data.models import Match, Team, TeamAlias
from bundespredict.data.team_aliases import UnmappedTeamError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "D1_9999.csv"


def _count(session: Session, model: type) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def test_ingest_returns_expected_counts(session: Session) -> None:
    stats = ingest_csv(session, FIXTURE)
    # 3 rows in the fixture, 1 postponed (blank scores) → 2 played matches.
    assert stats.matches_upserted == 2
    assert stats.teams_seen == 4
    assert stats.season == "9999"


def test_rows_land_in_postgres(session: Session) -> None:
    ingest_csv(session, FIXTURE)
    assert _count(session, Match) == 2
    assert _count(session, Team) == 4
    assert _count(session, TeamAlias) == 4


def test_no_null_scores(session: Session) -> None:
    ingest_csv(session, FIXTURE)
    null_scores = session.execute(
        select(func.count())
        .select_from(Match)
        .where((Match.home_goals.is_(None)) | (Match.away_goals.is_(None)))
    ).scalar_one()
    assert null_scores == 0


def test_team_names_are_canonical(session: Session) -> None:
    ingest_csv(session, FIXTURE)
    names = set(session.execute(select(Team.name)).scalars())
    assert names == {
        "Borussia Dortmund",
        "1.FC Köln",
        "Bayern Munich",
        "Bayer 04 Leverkusen",
    }


def test_alias_resolves_to_canonical_team(session: Session) -> None:
    ingest_csv(session, FIXTURE)
    alias = session.execute(select(TeamAlias).where(TeamAlias.alias == "FC Koln")).scalar_one()
    assert alias.source == "football-data"
    assert alias.team.name == "1.FC Köln"


def test_match_fields_persisted(session: Session) -> None:
    ingest_csv(session, FIXTURE)
    dortmund = session.execute(select(Team).where(Team.name == "Borussia Dortmund")).scalar_one()
    match = session.execute(select(Match).where(Match.home_id == dortmund.id)).scalar_one()
    assert (match.home_goals, match.away_goals, match.ftr) == (2, 1, "H")
    assert match.home_shots == 15
    assert match.b365_home == pytest.approx(1.50)


def test_reingest_is_idempotent(session: Session) -> None:
    ingest_csv(session, FIXTURE)
    ingest_csv(session, FIXTURE)
    # Re-running must not duplicate teams, aliases, or matches.
    assert _count(session, Match) == 2
    assert _count(session, Team) == 4
    assert _count(session, TeamAlias) == 4


def test_reingest_updates_changed_values(session: Session, tmp_path: Path) -> None:
    ingest_csv(session, FIXTURE)

    # Same fixture but the Dortmund–Köln score is corrected upstream.
    revised = tmp_path / "D1_9999.csv"
    revised.write_text(
        FIXTURE.read_text(encoding="latin-1").replace(
            "Dortmund,FC Koln,2,1,H", "Dortmund,FC Koln,4,0,H"
        ),
        encoding="latin-1",
    )
    ingest_csv(session, revised)

    assert _count(session, Match) == 2  # updated in place, not appended
    dortmund = session.execute(select(Team).where(Team.name == "Borussia Dortmund")).scalar_one()
    match = session.execute(select(Match).where(Match.home_id == dortmund.id)).scalar_one()
    assert (match.home_goals, match.away_goals) == (4, 0)


def test_unmapped_team_aborts_without_writing(session: Session, tmp_path: Path) -> None:
    bad = tmp_path / "D1_9997.csv"
    bad.write_text(
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n18/08/2023,Real Madrid,Dortmund,1,0,H\n",
        encoding="latin-1",
    )
    with pytest.raises(UnmappedTeamError):
        ingest_csv(session, bad)

    session.rollback()
    # Nothing was committed — not even the mappable team from the same file.
    assert _count(session, Match) == 0
    assert _count(session, Team) == 0
