"""Walk-forward backtest — fit on the past, predict the next gameweek, repeat.

This is the heart of the evaluation and the one place leakage discipline is
enforced end to end. For each gameweek we take a cutoff at the round's first
kickoff, fit
Dixon-Coles on *only* the matches played strictly before it (the loader's
``as_of_date`` filter guarantees this), shrink low-history teams, persist the run,
and predict that round's fixtures. Nothing from on or after the cutoff can touch
the fit, so every recorded prediction is one the model could genuinely have made
before the ball was kicked.

For each predicted match we keep the model's 1X2 probabilities, the de-vigged
market probabilities (the baseline to beat), the realized result, and the raw
Bet365 opening/closing odds (for the value-bet sim and CLV). Metrics, calibration
and betting all run downstream on these records — this module only produces them.

It is the DB seam for evaluation, like the loader: it talks to Postgres so the
``model/`` and the metric functions stay pure.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from bundespredict.data.loader import load_dated_matches
from bundespredict.data.models import Match, Team
from bundespredict.data.params_store import save_ratings
from bundespredict.eval.market import devig
from bundespredict.eval.metrics import encode_outcomes
from bundespredict.model.dixon_coles import fit_dixon_coles
from bundespredict.model.shrinkage import (
    DEFAULT_SHRINKAGE_K,
    shrink_ratings,
    team_match_counts,
)

logger = logging.getLogger(__name__)

# Decay rate the prior walk-forward xi-selection landed on (~173-day half-life).
# The reporting script can refine it via time_decay.select_xi and pass it in.
DEFAULT_XI = 0.004


@dataclass(frozen=True)
class _Fixture:
    season: str
    match_date: date
    home: str
    away: str
    ftr: str
    b365_open: tuple[float, float, float]
    b365_close: tuple[float, float, float]
    avg_open: tuple[float, float, float]
    avg_close: tuple[float, float, float]


@dataclass(frozen=True)
class BacktestResult:
    """Leakage-safe out-of-sample predictions, ready for metrics and betting.

    Every array is aligned by row to one predicted match. ``model_probs`` and the
    de-vigged ``market_probs_*`` are ``(N, 3)`` in ``[home, draw, away]`` order;
    the ``*_odds`` arrays carry the raw decimal Bet365 prices for the betting sim.
    """

    seasons: tuple[str, ...]
    dates: tuple[date, ...]
    home: tuple[str, ...]
    away: tuple[str, ...]
    outcomes: NDArray[np.intp]
    model_probs: NDArray[np.float64]
    market_probs_close: NDArray[np.float64]  # de-vigged Avg closing — primary baseline
    market_probs_open: NDArray[np.float64]  # de-vigged Avg opening
    bet_odds: NDArray[np.float64]  # Bet365 opening — the price we'd bet at
    close_odds: NDArray[np.float64]  # Bet365 closing — for CLV
    run_ids: tuple[int, ...]  # persisted model_run per predicted match (repeats per round)
    n_skipped_unseen: int  # fixtures dropped because a team had no prior history
    n_skipped_no_odds: int  # fixtures dropped for missing odds

    def __len__(self) -> int:
        return len(self.outcomes)


def _load_fixtures(session: Session, seasons: Sequence[str] | None) -> list[_Fixture]:
    """Pull every fixture (with names + odds) in date order for the backtest."""
    home_t = aliased(Team)
    away_t = aliased(Team)
    stmt = (
        select(
            Match.season,
            Match.date,
            home_t.name,
            away_t.name,
            Match.ftr,
            Match.b365_home,
            Match.b365_draw,
            Match.b365_away,
            Match.b365c_home,
            Match.b365c_draw,
            Match.b365c_away,
            Match.avg_home,
            Match.avg_draw,
            Match.avg_away,
            Match.avgc_home,
            Match.avgc_draw,
            Match.avgc_away,
        )
        .join(home_t, home_t.id == Match.home_id)
        .join(away_t, away_t.id == Match.away_id)
        .order_by(Match.date, Match.id)
    )
    if seasons is not None:
        stmt = stmt.where(Match.season.in_(seasons))

    fixtures: list[_Fixture] = []
    for row in session.execute(stmt):
        fixtures.append(
            _Fixture(
                season=row[0],
                match_date=row[1],
                home=row[2],
                away=row[3],
                ftr=row[4],
                b365_open=(row[5], row[6], row[7]),
                b365_close=(row[8], row[9], row[10]),
                avg_open=(row[11], row[12], row[13]),
                avg_close=(row[14], row[15], row[16]),
            )
        )
    return fixtures


def _assign_gameweeks(fixtures: list[_Fixture]) -> list[int]:
    """Group fixtures into rounds: a new round starts when a team would repeat.

    football-data has no matchday column, but a round-robin round is exactly the
    set of fixtures in which every club appears once. Walking date-ordered matches
    and opening a new round as soon as a team recurs reconstructs gameweeks
    robustly, including midweek rounds that a date-gap heuristic would mis-split.
    Numbering restarts each season.
    """
    gameweeks: list[int] = []
    gw = -1
    current_season: str | None = None
    used: set[str] = set()
    for fx in fixtures:
        if fx.season != current_season or fx.home in used or fx.away in used:
            gw += 1
            used = set()
            current_season = fx.season
        used.add(fx.home)
        used.add(fx.away)
        gameweeks.append(gw)
    return gameweeks


def _odds_ok(triple: tuple[float, float, float]) -> bool:
    return all(o is not None and o > 1.0 for o in triple)


def run_backtest(
    session: Session,
    *,
    seasons: Sequence[str] | None = None,
    predict_from_season: str | None = None,
    xi: float = DEFAULT_XI,
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
    min_train_matches: int = 200,
    persist: bool = True,
) -> BacktestResult:
    """Run the walk-forward backtest and return the out-of-sample records.

    The model is refit once per gameweek on all prior results. Predictions are
    recorded only from ``predict_from_season`` onward (default: the second season
    present), so every recorded fit has at least a season of history behind it;
    earlier gameweeks still run as warmup. Fixtures whose teams have no pre-cutoff
    history, or that lack odds, are skipped and counted.
    """
    fixtures = _load_fixtures(session, seasons)
    if not fixtures:
        raise ValueError("no fixtures matched the backtest filters")

    all_seasons = sorted({fx.season for fx in fixtures})
    if predict_from_season is None:
        predict_from_season = all_seasons[1] if len(all_seasons) > 1 else all_seasons[0]

    gameweeks = _assign_gameweeks(fixtures)

    # Bucket fixtures by gameweek, preserving date order.
    rounds: dict[int, list[_Fixture]] = {}
    for gw, fx in zip(gameweeks, fixtures, strict=True):
        rounds.setdefault(gw, []).append(fx)

    rec_season: list[str] = []
    rec_date: list[date] = []
    rec_home: list[str] = []
    rec_away: list[str] = []
    rec_ftr: list[str] = []
    rec_model: list[tuple[float, float, float]] = []
    rec_mkt_close: list[tuple[float, float, float]] = []
    rec_mkt_open: list[tuple[float, float, float]] = []
    rec_bet: list[tuple[float, float, float]] = []
    rec_clz: list[tuple[float, float, float]] = []
    rec_run: list[int] = []
    n_unseen = 0
    n_no_odds = 0

    for gw in sorted(rounds):
        round_fixtures = rounds[gw]
        cutoff = min(fx.match_date for fx in round_fixtures)
        recording = any(fx.season >= predict_from_season for fx in round_fixtures)

        try:
            dated = load_dated_matches(session, as_of_date=cutoff)
        except ValueError:
            continue  # no history yet — pure warmup
        if len(dated) < min_train_matches:
            continue

        data = dated.to_match_data(xi=xi, reference=cutoff)
        ratings = fit_dixon_coles(data)
        ratings = shrink_ratings(ratings, team_match_counts(data), k=shrinkage_k)

        if not recording:
            continue

        run_id = -1
        if persist:
            run_id = save_ratings(
                session,
                ratings,
                xi=xi,
                n_matches=len(dated),
                as_of_date=cutoff,
                version="walk-forward",
                notes=f"gameweek backtest, season {round_fixtures[0].season}",
            )

        for fx in round_fixtures:
            if fx.season < predict_from_season:
                continue
            if fx.home not in ratings.teams or fx.away not in ratings.teams:
                n_unseen += 1
                continue
            if not (_odds_ok(fx.avg_open) and _odds_ok(fx.avg_close) and _odds_ok(fx.b365_open)):
                n_no_odds += 1
                continue

            mk = ratings.predict(fx.home, fx.away)
            rec_model.append((mk.p_home, mk.p_draw, mk.p_away))
            rec_mkt_close.append(fx.avg_close)
            rec_mkt_open.append(fx.avg_open)
            rec_bet.append(fx.b365_open)
            rec_clz.append(fx.b365_close)
            rec_season.append(fx.season)
            rec_date.append(fx.match_date)
            rec_home.append(fx.home)
            rec_away.append(fx.away)
            rec_ftr.append(fx.ftr)
            rec_run.append(run_id)

        logger.info("gameweek %d (cutoff %s): %d recorded", gw, cutoff, len(rec_ftr))

    if not rec_model:
        raise ValueError("backtest produced no predictions; check the season window")

    return BacktestResult(
        seasons=tuple(rec_season),
        dates=tuple(rec_date),
        home=tuple(rec_home),
        away=tuple(rec_away),
        outcomes=encode_outcomes(rec_ftr),
        model_probs=np.array(rec_model, dtype=np.float64),
        market_probs_close=devig(np.array(rec_mkt_close, dtype=np.float64)),
        market_probs_open=devig(np.array(rec_mkt_open, dtype=np.float64)),
        bet_odds=np.array(rec_bet, dtype=np.float64),
        close_odds=np.array(rec_clz, dtype=np.float64),
        run_ids=tuple(rec_run),
        n_skipped_unseen=n_unseen,
        n_skipped_no_odds=n_no_odds,
    )
