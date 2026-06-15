"""Promoted-team shrinkage toward the league mean."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.model.dixon_coles import MatchData, TeamRatings
from bundespredict.model.shrinkage import (
    DEFAULT_SHRINKAGE_K,
    shrink_ratings,
    team_match_counts,
)


def _ratings(attack: list[float], defense: list[float]) -> TeamRatings:
    a = np.array(attack, dtype=np.float64)
    d = np.array(defense, dtype=np.float64)
    teams = tuple(f"T{i}" for i in range(len(attack)))
    return TeamRatings(
        teams=teams, attack=a, defense=d, home_adv=0.25, rho=-0.1, log_likelihood=-1.0
    )


def test_low_history_team_is_pulled_toward_zero() -> None:
    # A realistic league: team 0 is a promoted side with a big (over-fit) attack and
    # few matches; the other 17 are well-evidenced and share the opposite strength.
    n_others = 17
    attack = [0.6] + [-0.6 / n_others] * n_others
    ratings = _ratings(attack, [0.0] * (n_others + 1))
    counts = np.array([4] + [300] * n_others, dtype=np.intp)
    shrunk = shrink_ratings(ratings, counts, k=DEFAULT_SHRINKAGE_K)

    # The low-history team's attack magnitude shrinks markedly toward the mean.
    assert abs(shrunk.attack[0]) < abs(ratings.attack[0])
    # Well-evidenced teams barely move; re-centering only shifts everyone a touch.
    np.testing.assert_allclose(shrunk.attack[1:], ratings.attack[1:], atol=0.05)


def test_more_evidence_means_less_shrinkage() -> None:
    counts = np.array([3, 20, 200], dtype=np.intp)
    # The evidence weight applied to each team is monotone in its match count.
    w = counts / (counts + DEFAULT_SHRINKAGE_K)
    assert w[0] < w[1] < w[2]


def test_shrunk_ratings_keep_sum_to_zero_gauge() -> None:
    ratings = _ratings([0.6, -0.2, -0.4], [0.3, -0.1, -0.2])
    counts = np.array([5, 50, 150], dtype=np.intp)
    shrunk = shrink_ratings(ratings, counts)
    assert shrunk.attack.sum() == pytest.approx(0.0, abs=1e-12)
    assert shrunk.defense.sum() == pytest.approx(0.0, abs=1e-12)


def test_home_adv_and_rho_pass_through() -> None:
    ratings = _ratings([0.4, -0.4], [0.0, 0.0])
    shrunk = shrink_ratings(ratings, np.array([10, 10], dtype=np.intp))
    assert shrunk.home_adv == ratings.home_adv
    assert shrunk.rho == ratings.rho


def test_high_evidence_everywhere_is_near_identity() -> None:
    ratings = _ratings([0.3, -0.1, -0.2], [0.1, 0.0, -0.1])
    counts = np.array([500, 500, 500], dtype=np.intp)
    shrunk = shrink_ratings(ratings, counts, k=DEFAULT_SHRINKAGE_K)
    np.testing.assert_allclose(shrunk.attack, ratings.attack, atol=0.01)
    np.testing.assert_allclose(shrunk.defense, ratings.defense, atol=0.01)


def test_team_match_counts() -> None:
    data = MatchData(
        teams=("A", "B", "C"),
        home_idx=np.array([0, 1, 0], dtype=np.intp),
        away_idx=np.array([1, 2, 2], dtype=np.intp),
        home_goals=np.array([1, 0, 2], dtype=np.intp),
        away_goals=np.array([0, 0, 2], dtype=np.intp),
        weights=np.ones(3),
    )
    counts = team_match_counts(data)
    # A plays matches 0 and 2 (2), B plays 0 and 1 (2), C plays 1 and 2 (2).
    np.testing.assert_array_equal(counts, np.array([2, 2, 2]))


def test_length_mismatch_raises() -> None:
    ratings = _ratings([0.1, -0.1], [0.0, 0.0])
    with pytest.raises(ValueError, match="match_counts length"):
        shrink_ratings(ratings, np.array([1, 2, 3], dtype=np.intp))
