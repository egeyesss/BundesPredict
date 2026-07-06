"""Promoted-team shrinkage toward the league mean."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.model.dixon_coles import MatchData, TeamRatings
from bundespredict.model.shrinkage import (
    DEFAULT_SHRINKAGE_K,
    ShrinkTargets,
    shrink_ratings,
    team_match_counts,
    value_implied_targets,
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


def test_zero_targets_reproduce_plain_shrinkage() -> None:
    ratings = _ratings([0.6, -0.2, -0.4], [0.3, -0.1, -0.2])
    counts = np.array([5, 50, 150], dtype=np.intp)
    zeros = ShrinkTargets(attack=np.zeros(3), defense=np.zeros(3))
    plain = shrink_ratings(ratings, counts)
    targeted = shrink_ratings(ratings, counts, targets=zeros)
    np.testing.assert_allclose(targeted.attack, plain.attack)
    np.testing.assert_allclose(targeted.defense, plain.defense)


def test_zero_evidence_team_lands_on_its_target() -> None:
    # Constructed so the blended vector already sums to zero (targets equal the
    # fitted values for the high-evidence teams): re-centering is then a no-op
    # and the zero-evidence team's landing spot is exactly its target.
    ratings = _ratings([0.0, 0.3, -0.7], [0.0, 0.1, 0.1])
    counts = np.array([0, 10_000, 10_000], dtype=np.intp)
    targets = ShrinkTargets(attack=np.array([0.4, 0.3, -0.7]), defense=np.array([-0.2, 0.1, 0.1]))
    shrunk = shrink_ratings(ratings, counts, targets=targets)
    assert shrunk.attack[0] == pytest.approx(0.4, abs=1e-6)
    assert shrunk.defense[0] == pytest.approx(-0.2, abs=1e-6)
    # High-evidence teams keep their fitted strengths regardless of target.
    np.testing.assert_allclose(shrunk.attack[1:], ratings.attack[1:], atol=1e-2)


def test_targeted_shrinkage_keeps_gauge() -> None:
    ratings = _ratings([0.6, -0.2, -0.4], [0.3, -0.1, -0.2])
    counts = np.array([2, 40, 400], dtype=np.intp)
    targets = ShrinkTargets(attack=np.array([0.5, 0.0, 0.0]), defense=np.array([-0.3, 0.0, 0.0]))
    shrunk = shrink_ratings(ratings, counts, targets=targets)
    assert shrunk.attack.sum() == pytest.approx(0.0, abs=1e-12)
    assert shrunk.defense.sum() == pytest.approx(0.0, abs=1e-12)


def test_misaligned_targets_raise() -> None:
    ratings = _ratings([0.1, -0.1], [0.0, 0.0])
    bad = ShrinkTargets(attack=np.zeros(3), defense=np.zeros(3))
    with pytest.raises(ValueError, match="targets must align"):
        shrink_ratings(ratings, np.array([1, 2], dtype=np.intp), targets=bad)


def test_value_targets_recover_linear_relation() -> None:
    # Six trusted teams whose attack is exactly linear in log squad value, plus
    # a promoted team (few matches) whose fitted attack is way off the line.
    # The regression must ignore the outlier and read its target off the line.
    log_values = np.array(
        [
            np.log(50e6),
            np.log(100e6),
            np.log(200e6),
            np.log(400e6),
            np.log(800e6),
            np.log(25e6),
            np.log(100e6),
        ]
    )
    slope, mean_x = 0.3, log_values[:6].mean()
    attack = slope * (log_values - mean_x)
    attack[6] = 1.5  # nonsense over-fit from 3 matches
    ratings = _ratings(list(attack), list(-0.5 * (log_values - mean_x)))
    counts = np.array([100] * 6 + [3], dtype=np.intp)

    targets = value_implied_targets(ratings, counts, log_values, min_matches=20)
    # The promoted team's target sits on the trusted teams' regression line.
    assert targets.attack[6] == pytest.approx(slope * (log_values[6] - mean_x), abs=1e-6)
    assert targets.defense[6] == pytest.approx(-0.5 * (log_values[6] - mean_x), abs=1e-6)


def test_value_targets_missing_value_falls_back_to_league_mean() -> None:
    log_values = np.array([np.log(50e6), np.log(100e6), np.log(200e6), np.nan])
    ratings = _ratings([0.1, 0.2, 0.3, 0.9], [0.0, 0.0, 0.0, 0.0])
    counts = np.array([100, 100, 100, 2], dtype=np.intp)
    targets = value_implied_targets(ratings, counts, log_values, min_matches=20)
    assert targets.attack[3] == 0.0  # no value -> old prior (league mean)


def test_value_targets_too_few_trusted_teams_are_all_zero() -> None:
    log_values = np.log(np.array([50e6, 100e6, 200e6]))
    ratings = _ratings([0.3, -0.1, -0.2], [0.0, 0.0, 0.0])
    counts = np.array([5, 5, 100], dtype=np.intp)  # only one trusted team
    targets = value_implied_targets(ratings, counts, log_values, min_matches=20)
    np.testing.assert_array_equal(targets.attack, np.zeros(3))
    np.testing.assert_array_equal(targets.defense, np.zeros(3))
