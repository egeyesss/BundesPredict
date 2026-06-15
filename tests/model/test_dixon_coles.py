"""Correctness tests for the Dixon-Coles MLE.

The strongest of these is *parameter recovery*: generate matches from the model
with known strengths, refit, and assert we get them back. If that passes, the
hand-written likelihood and the optimizer wiring are almost certainly correct.
We also pin the rho=0 reduction to independent Poisson and basic monotonicity.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from bundespredict.model.dixon_coles import (
    MatchData,
    TeamRatings,
    fit_dixon_coles,
    fit_independent_poisson,
)
from bundespredict.model.markets import score_matrix


def _zero_sum(rng: np.random.Generator, n: int, scale: float) -> NDArray[np.float64]:
    """Random strengths centered to satisfy the sum-to-zero gauge the fit uses."""
    raw = rng.normal(0.0, scale, size=n)
    return np.asarray(raw - raw.mean(), dtype=np.float64)


def _simulate(
    attack: NDArray[np.float64],
    defense: NDArray[np.float64],
    home_adv: float,
    rho: float,
    *,
    rounds: int,
    rng: np.random.Generator,
) -> MatchData:
    """Generate a synthetic season: every ordered team pair plays ``rounds`` times.

    Scorelines are sampled from the true Dixon-Coles score matrix (so the tau
    correction is present in the data and rho is recoverable), capped at the same
    grid the engine uses.
    """
    n = len(attack)
    teams = tuple(f"T{i}" for i in range(n))
    home_idx, away_idx, home_goals, away_goals = [], [], [], []

    for _ in range(rounds):
        for h in range(n):
            for a in range(n):
                if h == a:
                    continue
                lam = float(np.exp(attack[h] + defense[a] + home_adv))
                mu = float(np.exp(attack[a] + defense[h]))
                matrix = score_matrix(lam, mu, rho=rho)
                # Sample one (i, j) cell from the flattened joint distribution.
                flat = rng.choice(matrix.size, p=matrix.ravel())
                i, j = np.unravel_index(flat, matrix.shape)
                home_idx.append(h)
                away_idx.append(a)
                home_goals.append(int(i))
                away_goals.append(int(j))

    size = len(home_idx)
    return MatchData(
        teams=teams,
        home_idx=np.array(home_idx, dtype=np.intp),
        away_idx=np.array(away_idx, dtype=np.intp),
        home_goals=np.array(home_goals, dtype=np.intp),
        away_goals=np.array(away_goals, dtype=np.intp),
        weights=np.ones(size, dtype=np.float64),
    )


def test_recovers_independent_poisson_parameters() -> None:
    rng = np.random.default_rng(7)
    n = 8
    attack = _zero_sum(rng, n, 0.35)
    defense = _zero_sum(rng, n, 0.30)
    home_adv = 0.28

    data = _simulate(attack, defense, home_adv, rho=0.0, rounds=60, rng=rng)
    fit = fit_independent_poisson(data)

    np.testing.assert_allclose(fit.attack, attack, atol=0.12)
    np.testing.assert_allclose(fit.defense, defense, atol=0.12)
    assert fit.home_adv == pytest.approx(home_adv, abs=0.06)
    assert fit.rho == 0.0


def test_recovers_dixon_coles_parameters_including_rho() -> None:
    rng = np.random.default_rng(11)
    n = 8
    attack = _zero_sum(rng, n, 0.35)
    defense = _zero_sum(rng, n, 0.30)
    home_adv = 0.26
    rho = -0.12

    data = _simulate(attack, defense, home_adv, rho=rho, rounds=80, rng=rng)
    fit = fit_dixon_coles(data)

    np.testing.assert_allclose(fit.attack, attack, atol=0.12)
    np.testing.assert_allclose(fit.defense, defense, atol=0.12)
    assert fit.home_adv == pytest.approx(home_adv, abs=0.06)
    assert fit.rho == pytest.approx(rho, abs=0.05)


def test_fitted_strengths_satisfy_sum_to_zero_gauge() -> None:
    rng = np.random.default_rng(3)
    n = 6
    data = _simulate(
        _zero_sum(rng, n, 0.3), _zero_sum(rng, n, 0.3), 0.25, rho=-0.1, rounds=40, rng=rng
    )
    fit = fit_dixon_coles(data)
    assert fit.attack.sum() == pytest.approx(0.0, abs=1e-9)
    assert fit.defense.sum() == pytest.approx(0.0, abs=1e-9)


def test_independent_fit_is_dixon_coles_with_rho_zero() -> None:
    """Reduction: forcing rho=0 in the fit must reproduce the independent fit."""
    rng = np.random.default_rng(5)
    n = 6
    data = _simulate(
        _zero_sum(rng, n, 0.3), _zero_sum(rng, n, 0.3), 0.25, rho=0.0, rounds=40, rng=rng
    )
    indep = fit_independent_poisson(data)
    assert indep.rho == 0.0
    # Its predictions use the rho=0 (independent) score matrix by construction.
    m = indep.predict("T0", "T1")
    assert m.p_home + m.p_draw + m.p_away == pytest.approx(1.0)


def test_stronger_attack_raises_home_win_probability() -> None:
    """Monotonicity: bump one team's attack, its home win prob must not fall."""
    teams = ("A", "B")
    base = TeamRatings(
        teams=teams,
        attack=np.array([0.0, 0.0]),
        defense=np.array([0.0, 0.0]),
        home_adv=0.25,
        rho=-0.1,
        log_likelihood=0.0,
    )
    stronger = TeamRatings(
        teams=teams,
        attack=np.array([0.4, -0.4]),
        defense=np.array([0.0, 0.0]),
        home_adv=0.25,
        rho=-0.1,
        log_likelihood=0.0,
    )
    base_p = base.predict("A", "B")
    strong_p = stronger.predict("A", "B")
    assert strong_p.p_home > base_p.p_home
    assert strong_p.exp_home_goals > base_p.exp_home_goals


def test_fit_rejects_single_team() -> None:
    data = MatchData(
        teams=("only",),
        home_idx=np.array([], dtype=np.intp),
        away_idx=np.array([], dtype=np.intp),
        home_goals=np.array([], dtype=np.intp),
        away_goals=np.array([], dtype=np.intp),
        weights=np.array([], dtype=np.float64),
    )
    with pytest.raises(ValueError, match="at least two teams"):
        fit_dixon_coles(data)
