"""Measure the value-implied shrinkage prior on promoted teams' early matches.

The prior only changes predictions where evidence is thin, so a whole-backtest
RPS comparison would drown the effect in ~1800 matches that barely move. The
honest measurement is the slice the change targets: **each promoted team's
first matches of its first season back up**. This script runs the walk-forward
backtest twice — league-mean shrinkage vs value-implied targets — and scores
both on exactly that slice (plus overall, to confirm nothing else regressed).

Promoted teams are read from the data itself: a club that plays in season S
but not in season S-1. Needs squad values in the DB (run
``scripts/scrape_transfermarkt.py`` first).
"""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.players import squad_values_by_season
from bundespredict.eval.backtest import BacktestResult, run_backtest
from bundespredict.eval.metrics import score_forecast

logger = logging.getLogger(__name__)

EARLY_MATCHES = 6  # per promoted team: the window where the prior can matter


def _promoted_mask(result: BacktestResult, teams_by_season: dict[str, set[str]]) -> np.ndarray:
    """Rows that involve a promoted team within its first EARLY_MATCHES games.

    Promotion = present in season S, absent from S-1 (the first season in the
    data has no predecessor and contributes nothing). Rows are date-ordered per
    team already, so "first N" is a simple counter.
    """
    seasons_sorted = sorted(teams_by_season)
    promoted: set[tuple[str, str]] = set()
    for prev, cur in zip(seasons_sorted, seasons_sorted[1:], strict=False):
        for team in teams_by_season[cur] - teams_by_season[prev]:
            promoted.add((cur, team))

    counter: dict[tuple[str, str], int] = defaultdict(int)
    mask = np.zeros(len(result), dtype=bool)
    order = np.argsort(
        np.array([d.toordinal() for d in result.dates], dtype=np.intp), kind="stable"
    )
    for i in order:
        season = result.seasons[i]
        for team in (result.home[i], result.away[i]):
            if (season, team) in promoted and counter[(season, team)] < EARLY_MATCHES:
                counter[(season, team)] += 1
                mask[i] = True
    return mask


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    engine = make_engine()
    with make_session_factory(engine)() as session:
        values = squad_values_by_season(session)
        if not values:
            raise SystemExit("no squad values in the DB — run scripts/scrape_transfermarkt.py")

        logger.info("backtest 1/2: league-mean shrinkage...")
        base = run_backtest(session, persist=False)
        logger.info("backtest 2/2: value-implied shrink targets...")
        prior = run_backtest(session, persist=False, squad_values=values)

    # Identical fixture streams in, so the rows align; assert rather than assume.
    if base.home != prior.home or base.dates != prior.dates:
        raise AssertionError("backtest rows diverged between runs")

    teams_by_season: dict[str, set[str]] = defaultdict(set)
    for season, home, away in zip(base.seasons, base.home, base.away, strict=True):
        teams_by_season[season].add(home)
        teams_by_season[season].add(away)
    mask = _promoted_mask(base, dict(teams_by_season))

    print(f"\npromoted-team early matches: {int(mask.sum())} of {len(base)} predictions")
    for label, result in (("league-mean prior", base), ("value-implied prior", prior)):
        sliced = score_forecast(result.model_probs[mask], result.outcomes[mask])
        overall = score_forecast(result.model_probs, result.outcomes)
        print(
            f"{label:>20}: promoted-slice RPS {sliced.rps:.4f} (log-loss {sliced.log_loss:.4f})"
            f" | overall RPS {overall.rps:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
