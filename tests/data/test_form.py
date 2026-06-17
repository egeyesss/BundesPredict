"""Postgres-backed tests for the recent-form lookup, incl. leakage filtering."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from bundespredict.data.form import recent_form
from bundespredict.data.models import Match, Team


def _seed(session: Session) -> None:
    """Alpha plays four matches across 2024; a mix of home/away, W/D/L."""
    a = Team(name="Alpha")
    b = Team(name="Beta")
    c = Team(name="Gamma")
    session.add_all([a, b, c])
    session.flush()

    session.add_all(
        [
            # Alpha home win 2-1 vs Beta
            Match(
                season="2324",
                date=date(2024, 3, 1),
                home_id=a.id,
                away_id=b.id,
                home_goals=2,
                away_goals=1,
                ftr="H",
            ),
            # Alpha away loss 0-3 at Gamma
            Match(
                season="2324",
                date=date(2024, 3, 8),
                home_id=c.id,
                away_id=a.id,
                home_goals=3,
                away_goals=0,
                ftr="H",
            ),
            # Alpha home draw 1-1 vs Gamma
            Match(
                season="2324",
                date=date(2024, 3, 15),
                home_id=a.id,
                away_id=c.id,
                home_goals=1,
                away_goals=1,
                ftr="D",
            ),
            # Alpha away win 2-0 at Beta (most recent)
            Match(
                season="2324",
                date=date(2024, 3, 22),
                home_id=b.id,
                away_id=a.id,
                home_goals=0,
                away_goals=2,
                ftr="A",
            ),
        ]
    )
    session.commit()


def test_form_aggregates_and_order(session: Session) -> None:
    _seed(session)
    form = recent_form(session, "Alpha", n=5)

    assert form.played == 4
    assert (form.wins, form.draws, form.losses) == (2, 1, 1)
    assert form.points == 7  # 2*3 + 1
    assert form.goals_for == 5  # 2 + 0 + 1 + 2
    assert form.goals_against == 5  # 1 + 3 + 1 + 0
    # Newest first: the away win at Beta.
    assert form.matches[0].opponent == "Beta"
    assert form.matches[0].venue == "A"
    assert form.matches[0].result == "W"
    assert form.matches[0].goals_for == 2


def test_form_respects_n_limit(session: Session) -> None:
    _seed(session)
    form = recent_form(session, "Alpha", n=2)
    assert form.played == 2
    # The two most recent: away win at Beta, then home draw vs Gamma.
    assert [m.result for m in form.matches] == ["W", "D"]


def test_form_as_of_date_excludes_on_and_after(session: Session) -> None:
    _seed(session)
    # As of the day of the last match, only the first three count (strictly before).
    form = recent_form(session, "Alpha", as_of_date=date(2024, 3, 22), n=5)
    assert form.played == 3
    assert all(m.date < date(2024, 3, 22) for m in form.matches)


def test_form_unknown_team_raises(session: Session) -> None:
    _seed(session)
    with pytest.raises(ValueError, match="unknown team"):
        recent_form(session, "Nonexistent")


def test_form_no_history_is_zeroed(session: Session) -> None:
    _seed(session)
    # A team that exists but has no matches before the cutoff.
    form = recent_form(session, "Alpha", as_of_date=date(2024, 1, 1), n=5)
    assert form.played == 0
    assert form.points == 0
    assert form.matches == ()
