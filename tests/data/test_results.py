"""Postgres-backed tests for the league-wide recent-results lookup."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from bundespredict.data.models import Match, Team
from bundespredict.data.results import latest_result_date, recent_results


def _seed(session: Session) -> None:
    a = Team(name="Alpha")
    b = Team(name="Beta")
    c = Team(name="Gamma")
    session.add_all([a, b, c])
    session.flush()
    session.add_all(
        [
            Match(
                season="2324",
                date=date(2024, 3, 1),
                home_id=a.id,
                away_id=b.id,
                home_goals=2,
                away_goals=1,
                ftr="H",
            ),
            Match(
                season="2324",
                date=date(2024, 3, 8),
                home_id=c.id,
                away_id=a.id,
                home_goals=3,
                away_goals=0,
                ftr="H",
            ),
            Match(
                season="2324",
                date=date(2024, 3, 15),
                home_id=b.id,
                away_id=c.id,
                home_goals=1,
                away_goals=1,
                ftr="D",
            ),
        ]
    )
    session.commit()


def test_recent_results_newest_first_with_names_and_scores(session: Session) -> None:
    _seed(session)
    rows = recent_results(session, n=2)
    assert len(rows) == 2
    assert rows[0].date == date(2024, 3, 15)
    assert (rows[0].home, rows[0].away) == ("Beta", "Gamma")
    assert (rows[0].home_goals, rows[0].away_goals) == (1, 1)
    assert rows[1].date == date(2024, 3, 8)


def test_recent_results_respects_as_of_date(session: Session) -> None:
    _seed(session)
    rows = recent_results(session, as_of_date=date(2024, 3, 8), n=10)
    # Strictly before: the March 8 match itself is excluded.
    assert [r.date for r in rows] == [date(2024, 3, 1)]


def test_latest_result_date(session: Session) -> None:
    assert latest_result_date(session) is None
    _seed(session)
    assert latest_result_date(session) == date(2024, 3, 15)
