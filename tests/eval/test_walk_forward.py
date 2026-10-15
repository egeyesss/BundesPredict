"""The walk-forward loop and report with the database replaced by in-memory callables.

This is the contract the Django backtest relies on: the loop only ever asks for history
before a round's cutoff, and everything it needs from storage goes through two callables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from bundespredict.data.dated_matches import DatedMatches, MatchRecord
from bundespredict.eval.backtest import BacktestFixture, BacktestResult, walk_forward
from bundespredict.eval.report import build_report
from bundespredict.model.dixon_coles import TeamRatings

TEAMS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
ODDS = (2.1, 3.3, 3.5)
SEASON_STARTS = (("2223", date(2022, 8, 6)), ("2324", date(2023, 8, 5)), ("2425", date(2024, 8, 3)))


def _rounds() -> list[list[tuple[str, str]]]:
    arr = list(TEAMS)
    first = []
    for _ in range(len(arr) - 1):
        first.append([(arr[i], arr[-1 - i]) for i in range(len(arr) // 2)])
        arr = [arr[0], arr[-1], *arr[1:-1]]
    return first + [[(away, home) for home, away in r] for r in first]


@dataclass
class League:
    fixtures: list[BacktestFixture]
    records: list[MatchRecord]
    cutoffs_asked: list[date]

    def load_history(self, cutoff: date) -> DatedMatches:
        self.cutoffs_asked.append(cutoff)
        return DatedMatches.from_records([r for r in self.records if r.played_on < cutoff])


@pytest.fixture
def league() -> League:
    rng = np.random.default_rng(5)
    fixtures: list[BacktestFixture] = []
    records: list[MatchRecord] = []
    for code, start in SEASON_STARTS:
        for number, pairs in enumerate(_rounds()):
            played_on = start + timedelta(days=7 * number)
            for home, away in pairs:
                home_goals, away_goals = int(rng.poisson(1.5)), int(rng.poisson(1.1))
                result = "H" if home_goals > away_goals else "A" if away_goals > home_goals else "D"
                fixtures.append(
                    BacktestFixture(code, played_on, home, away, result, ODDS, ODDS, ODDS, ODDS)
                )
                records.append(MatchRecord(home, away, home_goals, away_goals, played_on))
    return League(fixtures, records, [])


def _walk(league: League, saved: list[date] | None = None) -> BacktestResult:
    def save_run(
        ratings: TeamRatings, *, xi: float, n_matches: int, as_of_date: date, notes: str
    ) -> int:
        assert saved is not None
        saved.append(as_of_date)
        return len(saved)

    return walk_forward(
        league.fixtures,
        league.load_history,
        save_run if saved is not None else None,
        xi=0.004,
        min_train_matches=20,
    )


def test_every_fit_sees_only_matches_before_its_round(league: League) -> None:
    result = _walk(league)

    assert len(result) == 60  # two predicted seasons, ten rounds of three matches
    # Rounds are a week apart, so each round's first kickoff is its cutoff.
    assert set(league.cutoffs_asked) == {f.match_date for f in league.fixtures}


def test_one_run_is_saved_per_predicted_gameweek(league: League) -> None:
    saved: list[date] = []

    result = _walk(league, saved)

    assert len(saved) == 20
    assert result.run_ids == tuple(i for i in range(1, 21) for _ in range(3))


def test_without_a_saver_nothing_is_persisted(league: League) -> None:
    result = _walk(league)

    assert set(result.run_ids) == {-1}


def test_report_scores_the_run_and_writes_markdown(league: League, tmp_path: Path) -> None:
    result = _walk(league)
    xg_result = _walk(league)

    summary = build_report(result, xg_result, xi=0.004, reports_dir=tmp_path, plot=False)

    assert summary.n_predictions == 60
    assert summary.holdout_season == "2425"
    assert 0.0 < summary.model_rps < 1.0
    text = summary.report_path.read_text()
    assert "# Backtest report" in text
    assert "model (calibrated)" in text
    assert not (tmp_path / "reliability.png").exists()
