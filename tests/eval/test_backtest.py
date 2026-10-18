"""Gameweek grouping for the walk-forward backtest."""

from __future__ import annotations

from datetime import date, timedelta

from bundespredict.eval.backtest import BacktestFixture, _assign_gameweeks


def _fx(season: str, day: int, home: str, away: str) -> BacktestFixture:
    triple = (2.0, 3.3, 3.6)
    return BacktestFixture(
        season=season,
        match_date=date(2020, 1, 1) + timedelta(days=day),
        home=home,
        away=away,
        ftr="H",
        b365_open=triple,
        b365_close=triple,
        avg_open=triple,
        avg_close=triple,
    )


def test_assign_gameweeks_splits_on_team_repeat() -> None:
    # Two clean rounds of a 4-team league, then a season rollover.
    fixtures = [
        _fx("2001", 0, "A", "B"),
        _fx("2001", 0, "C", "D"),
        _fx("2001", 7, "A", "C"),
        _fx("2001", 7, "B", "D"),
        _fx("2002", 14, "A", "B"),
    ]
    assert _assign_gameweeks(fixtures) == [0, 0, 1, 1, 2]
