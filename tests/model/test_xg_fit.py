"""Correctness tests for the pre-match rolling-xG offset in the MLE.

Same philosophy as the core fit: the strongest signal is parameter recovery —
generate matches from a model with a known xG coefficient and per-match offsets,
refit, and get the coefficient back. Plus the reduction property: with the
feature switched off (or the coefficient zero) the model is exactly the
goals-only engine.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from bundespredict.model.dixon_coles import MatchData, TeamRatings, fit_dixon_coles
from bundespredict.model.markets import score_matrix


def _zero_sum(rng: np.random.Generator, n: int, scale: float) -> NDArray[np.float64]:
    raw = rng.normal(0.0, scale, size=n)
    return np.asarray(raw - raw.mean(), dtype=np.float64)


def _simulate_with_offsets(
    attack: NDArray[np.float64],
    defense: NDArray[np.float64],
    home_adv: float,
    rho: float,
    xg_coef: float,
    *,
    rounds: int,
    rng: np.random.Generator,
) -> MatchData:
    """Synthetic season where log-lambda carries ``xg_coef * offset`` per match.

    Offsets are drawn independently of the strengths so the coefficient is
    identified rather than absorbed into attack/defense.
    """
    n = len(attack)
    teams = tuple(f"T{i}" for i in range(n))
    home_idx, away_idx, home_goals, away_goals, home_off, away_off = [], [], [], [], [], []

    for _ in range(rounds):
        for h in range(n):
            for a in range(n):
                if h == a:
                    continue
                ho = float(rng.normal(0.0, 0.5))
                ao = float(rng.normal(0.0, 0.5))
                lam = float(np.exp(attack[h] + defense[a] + home_adv + xg_coef * ho))
                mu = float(np.exp(attack[a] + defense[h] + xg_coef * ao))
                matrix = score_matrix(lam, mu, rho=rho)
                flat = rng.choice(matrix.size, p=matrix.ravel())
                i, j = np.unravel_index(flat, matrix.shape)
                home_idx.append(h)
                away_idx.append(a)
                home_goals.append(int(i))
                away_goals.append(int(j))
                home_off.append(ho)
                away_off.append(ao)

    size = len(home_idx)
    return MatchData(
        teams=teams,
        home_idx=np.array(home_idx, dtype=np.intp),
        away_idx=np.array(away_idx, dtype=np.intp),
        home_goals=np.array(home_goals, dtype=np.intp),
        away_goals=np.array(away_goals, dtype=np.intp),
        weights=np.ones(size, dtype=np.float64),
        home_offset=np.array(home_off, dtype=np.float64),
        away_offset=np.array(away_off, dtype=np.float64),
    )


def test_recovers_xg_coefficient() -> None:
    rng = np.random.default_rng(19)
    n = 8
    attack = _zero_sum(rng, n, 0.35)
    defense = _zero_sum(rng, n, 0.30)
    home_adv = 0.27
    rho = -0.11
    xg_coef = 0.35

    data = _simulate_with_offsets(attack, defense, home_adv, rho, xg_coef, rounds=90, rng=rng)
    fit = fit_dixon_coles(data, use_xg=True)

    np.testing.assert_allclose(fit.attack, attack, atol=0.15)
    np.testing.assert_allclose(fit.defense, defense, atol=0.15)
    assert fit.home_adv == pytest.approx(home_adv, abs=0.06)
    assert fit.rho == pytest.approx(rho, abs=0.05)
    assert fit.xg_coef == pytest.approx(xg_coef, abs=0.1)


def test_zero_offsets_leave_the_coefficient_at_zero() -> None:
    """Reduction: with no xG signal in the data, the coefficient can't move off 0."""
    rng = np.random.default_rng(23)
    n = 6
    # Generate goals-only (true coef 0); the offsets carried are irrelevant here.
    data = _simulate_with_offsets(
        _zero_sum(rng, n, 0.3), _zero_sum(rng, n, 0.3), 0.25, -0.1, 0.0, rounds=40, rng=rng
    )
    # Force the offsets to exactly zero so the coefficient is unidentified and
    # the fit must leave it at its seed of 0.
    zeroed = MatchData(
        teams=data.teams,
        home_idx=data.home_idx,
        away_idx=data.away_idx,
        home_goals=data.home_goals,
        away_goals=data.away_goals,
        weights=data.weights,
        home_offset=np.zeros(len(data.home_idx)),
        away_offset=np.zeros(len(data.away_idx)),
    )
    fit = fit_dixon_coles(zeroed, use_xg=True)
    assert fit.xg_coef == pytest.approx(0.0, abs=1e-6)


def test_zero_coefficient_ignores_the_offset() -> None:
    """A goals-only rating (xg_coef=0) predicts identically regardless of offset."""
    ratings = TeamRatings(
        teams=("A", "B"),
        attack=np.array([0.3, -0.3]),
        defense=np.array([-0.1, 0.1]),
        home_adv=0.25,
        rho=-0.1,
        log_likelihood=0.0,
        xg_coef=0.0,
    )
    base = ratings.expected_goals("A", "B")
    with_off = ratings.expected_goals("A", "B", home_offset=1.5, away_offset=-1.5)
    assert base == with_off


def test_positive_coefficient_and_offset_raise_expected_goals() -> None:
    ratings = TeamRatings(
        teams=("A", "B"),
        attack=np.array([0.0, 0.0]),
        defense=np.array([0.0, 0.0]),
        home_adv=0.2,
        rho=-0.1,
        log_likelihood=0.0,
        xg_coef=0.4,
    )
    base_lambda, _ = ratings.expected_goals("A", "B")
    raised_lambda, _ = ratings.expected_goals("A", "B", home_offset=0.5)
    assert raised_lambda > base_lambda
