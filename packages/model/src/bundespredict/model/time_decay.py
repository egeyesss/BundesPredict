"""Time-decay weighting and walk-forward selection of the decay rate xi.

Recent matches carry more signal about current team strength, so Dixon-Coles
down-weights each match by ``exp(-xi * days_before)``. The catch is that xi is a
genuine hyperparameter: too aggressive and the effective sample shrinks and
estimates get noisy, too gentle and the model lags real changes in form. So we
**pick xi out-of-sample, not by intuition.**

A *single* train/holdout split is a trap here: the holdout sits immediately after
the cutoff, so heavier decay trivially looks better and the search runs off to an
absurdly short half-life. Instead we evaluate xi **walk-forward** — roll several
cutoffs across the recent data, fit on each cutoff's history and score only the
matches in the window right after it, then average. That mirrors how the model is
actually used (predict the next gameweek from the past) and yields an interior
optimum near the literature's ~0.003/day rather than a boundary value.

This stays pure: integer day-ordinals and arrays in, a chosen xi out. No dates,
no DB. The loader supplies the ordinals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from bundespredict.model.dixon_coles import (
    MatchData,
    fit_dixon_coles,
    match_log_likelihood,
)

# A reasonable sweep for multi-season league data. xi is per-day; 0 is no decay,
# ~0.003 is roughly a one-year half-life (the Dixon-Coles ballpark for ~5 seasons).
DEFAULT_XI_GRID: tuple[float, ...] = (0.0, 0.0005, 0.001, 0.002, 0.003, 0.004, 0.006)


def decay_weights(days_before: NDArray[np.float64], xi: float) -> NDArray[np.float64]:
    """Exponential time-decay weights. ``xi == 0`` yields all-ones (no decay)."""
    return np.asarray(np.exp(-xi * days_before), dtype=np.float64)


@dataclass(frozen=True)
class XiSelection:
    """Result of the walk-forward search: the winning xi and every candidate's score."""

    xi: float
    holdout_log_likelihood: float  # mean per-match LL of the winner, across all folds
    scores: tuple[tuple[float, float], ...]  # (xi, mean walk-forward log-likelihood)


def _fold_cutoffs(day_ordinal: NDArray[np.intp], n_folds: int, fold_days: int) -> list[int]:
    """Cutoff ordinals for the rolling folds, oldest first.

    The last fold scores ``[max - fold_days, max)``, the one before it the window
    before that, and so on for ``n_folds`` windows ending at the most recent match.
    """
    max_day = int(day_ordinal.max())
    return [max_day - k * fold_days for k in range(n_folds, 0, -1)]


def select_xi(
    teams: tuple[str, ...],
    home_idx: NDArray[np.intp],
    away_idx: NDArray[np.intp],
    home_goals: NDArray[np.intp],
    away_goals: NDArray[np.intp],
    day_ordinal: NDArray[np.intp],
    *,
    n_folds: int = 6,
    fold_days: int = 60,
    xi_grid: tuple[float, ...] = DEFAULT_XI_GRID,
) -> XiSelection:
    """Choose xi by maximizing mean walk-forward log-likelihood.

    For each of ``n_folds`` rolling cutoffs (each ``fold_days`` wide, covering the
    most recent ``n_folds * fold_days`` days), fit Dixon-Coles on the matches
    *before* the cutoff with the candidate decay, then score only the matches in
    the window *after* it — unweighted, so it's a clean out-of-sample read. The
    candidate's score is the pooled per-match log-likelihood over every fold.

    The cutoffs are strictly by date, so no future result ever informs a fit. This
    is the same leakage discipline as the Phase-3 backtest, just used here to tune
    one hyperparameter.
    """
    if len(home_idx) == 0:
        raise ValueError("no matches to select xi from")

    cutoffs = _fold_cutoffs(day_ordinal, n_folds, fold_days)
    # Build the (train mask, score mask) per fold once; they don't depend on xi.
    folds: list[tuple[NDArray[np.bool_], NDArray[np.bool_]]] = []
    for cutoff in cutoffs:
        train_mask = day_ordinal < cutoff
        score_mask = (day_ordinal >= cutoff) & (day_ordinal < cutoff + fold_days)
        if train_mask.any() and score_mask.any():
            folds.append((train_mask, score_mask))
    if not folds:
        raise ValueError("not enough history for the requested folds")

    scores: list[tuple[float, float]] = []
    for xi in xi_grid:
        total_ll = 0.0
        total_matches = 0
        for train_mask, score_mask in folds:
            cutoff = int(day_ordinal[score_mask].min())
            train_days_before = (cutoff - day_ordinal[train_mask]).astype(np.float64)
            train = MatchData(
                teams=teams,
                home_idx=home_idx[train_mask],
                away_idx=away_idx[train_mask],
                home_goals=home_goals[train_mask],
                away_goals=away_goals[train_mask],
                weights=decay_weights(train_days_before, xi),
            )
            holdout = MatchData(
                teams=teams,
                home_idx=home_idx[score_mask],
                away_idx=away_idx[score_mask],
                home_goals=home_goals[score_mask],
                away_goals=away_goals[score_mask],
                weights=np.ones(int(score_mask.sum()), dtype=np.float64),
            )
            ratings = fit_dixon_coles(train)
            total_ll += match_log_likelihood(ratings, holdout)
            total_matches += len(holdout.home_idx)
        scores.append((xi, total_ll / total_matches))

    best_xi, best_ll = max(scores, key=lambda s: s[1])
    return XiSelection(xi=best_xi, holdout_log_likelihood=best_ll, scores=tuple(scores))
