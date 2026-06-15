"""Time-decay weighting and holdout xi-selection."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.model.markets import score_matrix
from bundespredict.model.time_decay import decay_weights, select_xi


def test_decay_weights_basic_shape() -> None:
    days = np.array([0.0, 100.0, 200.0], dtype=np.float64)
    # xi=0 -> all ones (no decay).
    np.testing.assert_allclose(decay_weights(days, 0.0), np.ones(3))
    # Positive xi -> strictly decreasing as days_before grows, newest weight 1.
    w = decay_weights(days, 0.003)
    assert w[0] == pytest.approx(1.0)
    assert w[0] > w[1] > w[2] > 0.0


def _simulate_dated(
    rng: np.random.Generator,
    *,
    n_teams: int,
    rounds: int,
    span_days: int,
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic matches spread evenly over a date span, sampled from the model."""
    attack = rng.normal(0.0, 0.3, n_teams)
    attack -= attack.mean()
    defense = rng.normal(0.0, 0.3, n_teams)
    defense -= defense.mean()
    home_adv, rho = 0.25, -0.12
    teams = tuple(f"T{i}" for i in range(n_teams))

    hi, ai, hg, ag, days = [], [], [], [], []
    fixtures = [(h, a) for h in range(n_teams) for a in range(n_teams) if h != a]
    n_total = rounds * len(fixtures)
    ordinals = np.linspace(0, span_days, n_total).astype(int)

    k = 0
    for _ in range(rounds):
        for h, a in fixtures:
            lam = float(np.exp(attack[h] + defense[a] + home_adv))
            mu = float(np.exp(attack[a] + defense[h]))
            matrix = score_matrix(lam, mu, rho=rho)
            flat = rng.choice(matrix.size, p=matrix.ravel())
            i, j = np.unravel_index(flat, matrix.shape)
            hi.append(h)
            ai.append(a)
            hg.append(int(i))
            ag.append(int(j))
            days.append(int(ordinals[k]))
            k += 1

    return (
        teams,
        np.array(hi, dtype=np.intp),
        np.array(ai, dtype=np.intp),
        np.array(hg, dtype=np.intp),
        np.array(ag, dtype=np.intp),
        np.array(days, dtype=np.intp),
    )


def test_select_xi_returns_a_grid_candidate() -> None:
    rng = np.random.default_rng(19)
    teams, hi, ai, hg, ag, days = _simulate_dated(rng, n_teams=6, rounds=40, span_days=1500)
    result = select_xi(teams, hi, ai, hg, ag, days, n_folds=4, fold_days=80)

    candidate_xis = {xi for xi, _ in result.scores}
    assert result.xi in candidate_xis
    # The winner really is the argmax over the scored grid.
    assert result.holdout_log_likelihood == max(ll for _, ll in result.scores)


def test_select_xi_recovers_no_decay_when_strengths_are_stationary() -> None:
    """Data generated from fixed strengths has no real time signal, so the
    walk-forward search should not prefer aggressive decay over xi=0."""
    rng = np.random.default_rng(23)
    teams, hi, ai, hg, ag, days = _simulate_dated(rng, n_teams=6, rounds=60, span_days=2000)
    result = select_xi(
        teams, hi, ai, hg, ag, days, n_folds=5, fold_days=80, xi_grid=(0.0, 0.003, 0.02)
    )
    # The heaviest decay must not win on stationary data — that was the single
    # -split pathology this walk-forward design removes.
    assert result.xi < 0.02


def test_select_xi_rejects_insufficient_history() -> None:
    rng = np.random.default_rng(2)
    teams, hi, ai, hg, ag, days = _simulate_dated(rng, n_teams=4, rounds=10, span_days=300)
    # Folds reaching far past the data leave no usable train/score windows.
    with pytest.raises(ValueError, match="not enough history"):
        select_xi(teams, hi, ai, hg, ag, days, n_folds=6, fold_days=10_000)
