"""Walk-forward backtest on the Django models, persisting one `ModelRun` per gameweek.

The loop itself lives in the library (`bundespredict.eval.backtest.walk_forward`); this module
supplies the database side: fixtures with odds, history before a cutoff, and a store that reuses
walk-forward runs that already hold identical parameters so a re-run changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import cast

from django.db import transaction

from bundespredict.data.dated_matches import DatedMatches
from bundespredict.eval.backtest import BacktestFixture, BacktestResult, walk_forward
from bundespredict.model.dixon_coles import TeamRatings
from football.models import Match, ModelRun

from .training import (
    load_dated_matches,
    run_matches_ratings,
    save_model_run,
    squad_values_for_season,
)

WALK_FORWARD_VERSION = "walk-forward"

Odds = tuple[float, float, float]


def load_backtest_fixtures() -> list[BacktestFixture]:
    """Every match with names and odds, in date order, as the backtest consumes them."""
    rows = Match.objects.order_by("date", "id").values_list(
        "season",
        "date",
        "home__name",
        "away__name",
        "ftr",
        "b365_home",
        "b365_draw",
        "b365_away",
        "b365c_home",
        "b365c_draw",
        "b365c_away",
        "avg_home",
        "avg_draw",
        "avg_away",
        "avgc_home",
        "avgc_draw",
        "avgc_away",
    )
    # The odds columns are nullable; `walk_forward` drops matches missing odds before using them.
    return [
        BacktestFixture(
            season=r[0],
            match_date=r[1],
            home=r[2],
            away=r[3],
            ftr=r[4],
            b365_open=cast(Odds, tuple(r[5:8])),
            b365_close=cast(Odds, tuple(r[8:11])),
            avg_open=cast(Odds, tuple(r[11:14])),
            avg_close=cast(Odds, tuple(r[14:17])),
        )
        for r in rows
    ]


@dataclass(frozen=True)
class WalkForwardRuns:
    reused: int
    created: int
    removed: int


class WalkForwardStore:
    """Persists walk-forward runs, keeping any existing run that already matches.

    Runs are keyed by cutoff date and notes. A run that matches is left untouched, so ids stay
    stable; anything left over after the backtest (a changed fit, a dropped gameweek) is pruned.
    `trained_at` is set to the cutoff because the run is what a model trained that day would
    have been, and it keeps `latest_model_run()` pointing at the serving fit.
    """

    def __init__(self) -> None:
        self._existing: dict[tuple[date | None, str | None], ModelRun] = {
            (run.as_of_date, run.notes): run
            for run in ModelRun.objects.filter(version=WALK_FORWARD_VERSION)
        }
        self._kept: set[int] = set()
        self._created = 0
        self._reused = 0

    def save(
        self, ratings: TeamRatings, *, xi: float, n_matches: int, as_of_date: date, notes: str
    ) -> int:
        current = self._existing.get((as_of_date, notes))
        if (
            current is not None
            and current.n_matches == n_matches
            and run_matches_ratings(current, ratings, xi=xi)
        ):
            self._kept.add(current.id)
            self._reused += 1
            return current.id
        run = save_model_run(
            ratings,
            xi=xi,
            n_matches=n_matches,
            as_of_date=as_of_date,
            version=WALK_FORWARD_VERSION,
            notes=notes,
        )
        ModelRun.objects.filter(id=run.id).update(
            trained_at=datetime.combine(as_of_date, datetime.min.time(), tzinfo=UTC)
        )
        self._kept.add(run.id)
        self._created += 1
        return run.id

    def prune(self) -> WalkForwardRuns:
        with transaction.atomic():
            stale = ModelRun.objects.filter(version=WALK_FORWARD_VERSION).exclude(id__in=self._kept)
            removed = stale.count()
            stale.delete()
        return WalkForwardRuns(self._reused, self._created, removed)


def run_walk_forward(
    *,
    xi: float,
    min_train_matches: int,
    store: WalkForwardStore | None,
    use_xg: bool = False,
) -> BacktestResult:
    """Run the walk-forward over every stored match; `store=None` leaves the database alone."""
    values_by_season = {
        season: squad_values_for_season(season)
        for season in Match.objects.values_list("season", flat=True).distinct()
    }

    def load_history(cutoff: date) -> DatedMatches:
        return load_dated_matches(as_of=cutoff)

    return walk_forward(
        load_backtest_fixtures(),
        load_history,
        store.save if store is not None else None,
        xi=xi,
        min_train_matches=min_train_matches,
        squad_values={s: v for s, v in values_by_season.items() if v} or None,
        use_xg=use_xg,
    )
