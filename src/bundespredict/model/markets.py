"""Score matrix and market slicing — the pure heart of the predictor.

One joint distribution over scorelines, ``P(home=i, away=j)``, is built from two
expected-goals rates. *Every* market is then a slice of that single matrix: 1X2
is the three triangles, over/under is an anti-diagonal split, BTTS is the
``i>=1, j>=1`` block, a correct score is one cell. That "one distribution, many
markets" structure mirrors how a real book prices a match.

No I/O, no DB, no LLM — given two lambdas (and optionally Dixon-Coles ``rho``)
this returns probabilities. The Dixon-Coles low-score correction lives here too,
gated behind ``rho``: at ``rho == 0`` the matrix is exactly the independent
Poisson outer product, which is the golden reduction the tests pin down.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.stats import poisson

# Goals beyond ~10 carry negligible mass for football lambdas (~1-2), so we
# truncate there and renormalize. 0..10 inclusive => an 11x11 matrix.
DEFAULT_MAX_GOALS = 10


def _apply_dc_correction(
    matrix: NDArray[np.float64], lambda_home: float, lambda_away: float, rho: float
) -> None:
    """Apply the Dixon-Coles tau correction to the four low-score cells in place.

    Independent Poisson underestimates the dependence in low-scoring games (the
    0-0/1-0/0-1/1-1 cluster, draws especially). Dixon-Coles multiplies just those
    four cells by tau; every other cell is untouched (tau = 1). With the original
    paper's ``rho`` ~ -0.13 this lifts 0-0 and 1-1 and trims 1-0/0-1.
    """
    lam, mu = lambda_home, lambda_away
    matrix[0, 0] *= 1.0 - lam * mu * rho
    matrix[0, 1] *= 1.0 + lam * rho
    matrix[1, 0] *= 1.0 + mu * rho
    matrix[1, 1] *= 1.0 - rho


def score_matrix(
    lambda_home: float,
    lambda_away: float,
    *,
    rho: float = 0.0,
    max_goals: int = DEFAULT_MAX_GOALS,
) -> NDArray[np.float64]:
    """Joint scoreline distribution ``P(home=i, away=j)`` for i,j in 0..max_goals.

    Home and away goals are independent Poisson with the given means; the optional
    Dixon-Coles ``rho`` adjusts the four low-score cells. The result is
    renormalized to sum to 1 because both the truncation at ``max_goals`` and the
    tau correction perturb the total slightly. ``rho == 0`` returns the plain
    independent-Poisson matrix (the reduction the tests rely on).
    """
    goals = np.arange(max_goals + 1)
    home_pmf = poisson.pmf(goals, lambda_home)
    away_pmf = poisson.pmf(goals, lambda_away)
    matrix = np.outer(home_pmf, away_pmf)

    if rho != 0.0:
        _apply_dc_correction(matrix, lambda_home, lambda_away, rho)

    total = matrix.sum()
    return np.asarray(matrix / total, dtype=np.float64)


@dataclass(frozen=True)
class Markets:
    """Probabilities sliced from one score matrix. Immutable: a pure view of it."""

    p_home: float
    p_draw: float
    p_away: float
    p_over_2_5: float
    p_under_2_5: float
    p_btts: float  # both teams to score
    exp_home_goals: float
    exp_away_goals: float
    # Most likely exact scorelines: (home_goals, away_goals, probability), descending.
    top_scores: tuple[tuple[int, int, float], ...]


def markets_from_matrix(matrix: NDArray[np.float64], *, top_n: int = 5) -> Markets:
    """Slice all supported markets out of a score matrix.

    Conventions: rows index home goals, columns away goals. The matrix is assumed
    already normalized (as returned by :func:`score_matrix`); expectations are
    taken over it so they stay self-consistent with the truncated distribution
    rather than echoing the raw input lambdas.
    """
    n = matrix.shape[0]
    home_goals = np.arange(n)

    # 1X2: home win is the strictly-lower triangle (i > j), away win the strictly
    # -upper triangle, draw the diagonal.
    p_home = float(np.tril(matrix, k=-1).sum())
    p_away = float(np.triu(matrix, k=1).sum())
    p_draw = float(np.trace(matrix))

    # Over/Under 2.5: split on total goals i + j. The 2.5 line can't push.
    totals = home_goals[:, None] + home_goals[None, :]
    p_over = float(matrix[totals >= 3].sum())
    p_under = float(matrix[totals <= 2].sum())

    # BTTS: both score at least once => drop row 0 and column 0.
    p_btts = float(matrix[1:, 1:].sum())

    # Expected goals from the (truncated, normalized) marginals.
    exp_home = float(home_goals @ matrix.sum(axis=1))
    exp_away = float(home_goals @ matrix.sum(axis=0))

    top_scores = _top_scores(matrix, top_n)

    return Markets(
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        p_over_2_5=p_over,
        p_under_2_5=p_under,
        p_btts=p_btts,
        exp_home_goals=exp_home,
        exp_away_goals=exp_away,
        top_scores=top_scores,
    )


def _top_scores(matrix: NDArray[np.float64], top_n: int) -> tuple[tuple[int, int, float], ...]:
    """Return the ``top_n`` most probable exact scorelines, most likely first."""
    flat_order = np.argsort(matrix, axis=None)[::-1][:top_n]
    rows, cols = np.unravel_index(flat_order, matrix.shape)
    return tuple((int(i), int(j), float(matrix[i, j])) for i, j in zip(rows, cols, strict=True))


def markets(
    lambda_home: float,
    lambda_away: float,
    *,
    rho: float = 0.0,
    max_goals: int = DEFAULT_MAX_GOALS,
    top_n: int = 5,
) -> Markets:
    """Convenience: build the score matrix and slice every market in one call."""
    matrix = score_matrix(lambda_home, lambda_away, rho=rho, max_goals=max_goals)
    return markets_from_matrix(matrix, top_n=top_n)
