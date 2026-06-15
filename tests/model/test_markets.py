"""Invariants for the score matrix and the markets sliced from it.

These are the cheap structural guarantees from the build plan: the matrix is a
proper distribution, mutually exclusive/exhaustive markets sum to 1, and the
Dixon-Coles correction reduces to independent Poisson at rho=0.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import poisson

from bundespredict.model.markets import (
    markets,
    markets_from_matrix,
    score_matrix,
)

# A spread of realistic-to-lopsided rates so invariants are checked off the
# central case, not just near it.
LAMBDA_PAIRS = [
    (1.5, 1.2),
    (0.4, 0.4),
    (2.8, 0.6),
    (1.0, 1.0),
    (3.5, 3.5),
]


@pytest.mark.parametrize(("lh", "la"), LAMBDA_PAIRS)
@pytest.mark.parametrize("rho", [0.0, -0.13, 0.08])
def test_score_matrix_is_a_distribution(lh: float, la: float, rho: float) -> None:
    matrix = score_matrix(lh, la, rho=rho)
    assert matrix.shape == (11, 11)
    assert np.all(matrix >= 0.0), "no negative probabilities"
    assert matrix.sum() == pytest.approx(1.0), "cells sum to 1 after renormalization"


@pytest.mark.parametrize(("lh", "la"), LAMBDA_PAIRS)
def test_rho_zero_reduces_to_independent_poisson(lh: float, la: float) -> None:
    """The golden reduction: rho=0 is exactly the outer product of the marginals."""
    goals = np.arange(11)
    independent = np.outer(poisson.pmf(goals, lh), poisson.pmf(goals, la))
    independent /= independent.sum()  # match the truncation+renormalization

    np.testing.assert_allclose(score_matrix(lh, la, rho=0.0), independent, atol=1e-12)


@pytest.mark.parametrize(("lh", "la"), LAMBDA_PAIRS)
@pytest.mark.parametrize("rho", [0.0, -0.13])
def test_1x2_sums_to_one(lh: float, la: float, rho: float) -> None:
    m = markets(lh, la, rho=rho)
    assert m.p_home + m.p_draw + m.p_away == pytest.approx(1.0)


@pytest.mark.parametrize(("lh", "la"), LAMBDA_PAIRS)
@pytest.mark.parametrize("rho", [0.0, -0.13])
def test_over_under_sums_to_one(lh: float, la: float, rho: float) -> None:
    m = markets(lh, la, rho=rho)
    assert m.p_over_2_5 + m.p_under_2_5 == pytest.approx(1.0)


def test_dc_correction_lifts_draws_for_negative_rho() -> None:
    """With rho<0 the model should put *more* mass on draws than independent."""
    lh, la = 1.4, 1.3
    indep = markets(lh, la, rho=0.0)
    corrected = markets(lh, la, rho=-0.13)
    assert corrected.p_draw > indep.p_draw


def test_btts_matches_complement_of_a_clean_sheet() -> None:
    """BTTS == 1 - P(either side keeps a clean sheet); cross-check the block sum."""
    lh, la = 1.6, 1.1
    matrix = score_matrix(lh, la, rho=-0.13)
    m = markets_from_matrix(matrix)
    p_home_clean = matrix[:, 0].sum()  # away scored 0
    p_away_clean = matrix[0, :].sum()  # home scored 0
    p_no_goals = matrix[0, 0]
    clean_sheet = p_home_clean + p_away_clean - p_no_goals  # inclusion-exclusion
    assert m.p_btts == pytest.approx(1.0 - clean_sheet)


def test_top_scores_are_sorted_and_consistent() -> None:
    m = markets(1.5, 1.2, rho=-0.13, top_n=5)
    probs = [p for _, _, p in m.top_scores]
    assert probs == sorted(probs, reverse=True)
    assert len(m.top_scores) == 5
    # The most likely scoreline's probability matches the matrix cell.
    matrix = score_matrix(1.5, 1.2, rho=-0.13)
    i, j, p = m.top_scores[0]
    assert p == pytest.approx(matrix[i, j])
    assert p == pytest.approx(matrix.max())


def test_stronger_home_side_has_higher_home_win_prob() -> None:
    """Monotonicity sanity: a bigger home lambda must not lower P(home win)."""
    weak = markets(1.2, 1.2, rho=-0.13)
    strong = markets(2.0, 1.2, rho=-0.13)
    assert strong.p_home > weak.p_home
    assert strong.exp_home_goals > weak.exp_home_goals
