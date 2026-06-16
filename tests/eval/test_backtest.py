"""Tests for the walk-forward backtest: gameweek grouping + leakage discipline."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.data.models import Match, ModelRun, Team
from bundespredict.eval.backtest import (
    _assign_gameweeks,
    _Fixture,
    run_backtest,
)


def _fx(season: str, day: int, home: str, away: str) -> _Fixture:
    triple = (2.0, 3.3, 3.6)
    return _Fixture(
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


def _round_robin(teams: list[str]) -> list[list[tuple[str, str]]]:
    """Single round-robin schedule via the circle method (each team once/round)."""
    n = len(teams)
    arr = list(teams)
    rounds: list[list[tuple[str, str]]] = []
    for _ in range(n - 1):
        pairs = [(arr[i], arr[n - 1 - i]) for i in range(n // 2)]
        rounds.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]  # rotate, fixing the first
    return rounds


def _seed_two_seasons(session: Session) -> None:
    names = ["Alpha FC", "Beta FC", "Gamma FC", "Delta FC", "Epsilon FC", "Zeta FC"]
    session.add_all([Team(name=n) for n in names])
    session.commit()
    name_to_id = {n: i for i, n in session.execute(select(Team.id, Team.name)).tuples().all()}

    rng = np.random.default_rng(3)
    schedule = _round_robin(names)
    triple_open = (2.10, 3.30, 3.50)
    triple_close = (2.05, 3.40, 3.55)
    matches: list[Match] = []
    for season, year in (("2001", 2020), ("2002", 2021)):
        for rnd, pairs in enumerate(schedule):
            d = date(year, 8, 1) + timedelta(days=rnd * 7)
            for home, away in pairs:
                hg, ag = int(rng.integers(0, 4)), int(rng.integers(0, 4))
                ftr = "H" if hg > ag else "A" if ag > hg else "D"
                matches.append(
                    Match(
                        season=season,
                        date=d,
                        home_id=name_to_id[home],
                        away_id=name_to_id[away],
                        home_goals=hg,
                        away_goals=ag,
                        ftr=ftr,
                        b365_home=triple_open[0],
                        b365_draw=triple_open[1],
                        b365_away=triple_open[2],
                        b365c_home=triple_close[0],
                        b365c_draw=triple_close[1],
                        b365c_away=triple_close[2],
                        avg_home=triple_open[0],
                        avg_draw=triple_open[1],
                        avg_away=triple_open[2],
                        avgc_home=triple_close[0],
                        avgc_draw=triple_close[1],
                        avgc_away=triple_close[2],
                    )
                )
    session.add_all(matches)
    session.commit()


def test_backtest_runs_walk_forward_without_leakage(session: Session) -> None:
    _seed_two_seasons(session)
    result = run_backtest(
        session,
        predict_from_season="2002",
        xi=0.0,
        min_train_matches=5,
        persist=True,
    )

    # Season 2 is six teams over five rounds of three matches = 15 fixtures, all
    # with prior history, so nothing is skipped.
    assert len(result) == 15
    assert result.n_skipped_unseen == 0
    assert result.n_skipped_no_odds == 0
    assert set(result.seasons) == {"2002"}

    # Probabilities are well-formed.
    assert result.model_probs.shape == (15, 3)
    assert result.model_probs.sum(axis=1) == pytest.approx(np.ones(15))
    assert result.market_probs_close.sum(axis=1) == pytest.approx(np.ones(15))

    # The non-negotiable check: every prediction used a fit whose cutoff is the
    # round's first kickoff, and the loader filters matches *strictly* before the
    # cutoff (covered in test_loader). So the cutoff is on-or-before the match
    # date and the match's own result never fed its fit — no leakage.
    runs = {r.id: r for r in session.execute(select(ModelRun)).scalars()}
    for run_id, match_date in zip(result.run_ids, result.dates, strict=True):
        cutoff = runs[run_id].as_of_date
        assert cutoff is not None
        assert cutoff <= match_date


def test_backtest_persists_one_run_per_gameweek(session: Session) -> None:
    _seed_two_seasons(session)
    run_backtest(session, predict_from_season="2002", xi=0.0, min_train_matches=5)
    # Five recorded gameweeks in season 2 -> five persisted runs, each with all
    # six teams' parameters.
    n_runs = session.query(ModelRun).count()
    assert n_runs == 5
    run = session.query(ModelRun).first()
    assert run is not None
    assert len(run.team_params) == 6
    assert run.model_type == "dixon_coles"
