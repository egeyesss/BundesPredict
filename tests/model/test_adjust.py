"""Tests for the expected-goals adjustment apply-path.

The non-negotiable ones: clamping (an absurd request can't move goals past the
bound) and the lambda floor (a big negative can't drive a low-rate team to a
non-positive Poisson mean). Plus routing, monotonicity, and the rule that
disciplinary targets never touch the 1X2 result.
"""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.model.adjust import (
    LAMBDA_FLOOR,
    MAGNITUDE_BOUND,
    GoalAdjustment,
    adjusted_expected_goals,
    clamp_magnitude,
    predict_adjusted,
    resolve_goal_deltas,
)
from bundespredict.model.dixon_coles import TeamRatings


def _ratings(*, home_adv: float = 0.25, rho: float = -0.12) -> TeamRatings:
    """A small fitted-shaped ratings object: a strong side and a weak side."""
    return TeamRatings(
        teams=("strong", "weak"),
        attack=np.array([0.5, -0.5]),
        defense=np.array([-0.3, 0.3]),
        home_adv=home_adv,
        rho=rho,
        log_likelihood=0.0,
    )


# --- clamping -------------------------------------------------------------


def test_clamp_caps_absurd_request_at_bound() -> None:
    assert clamp_magnitude(5.0) == MAGNITUDE_BOUND
    assert clamp_magnitude(-5.0) == -MAGNITUDE_BOUND


def test_clamp_passes_through_in_range() -> None:
    assert clamp_magnitude(0.3) == 0.3
    assert clamp_magnitude(-0.45) == -0.45


def test_resolve_clamps_each_magnitude_before_summing() -> None:
    # Two +5.0 home_attack requests can move home goals by at most 2 * bound,
    # never 10.
    delta = resolve_goal_deltas([("home_attack", 5.0), ("home_attack", 5.0)])
    assert delta.home_delta == pytest.approx(2 * MAGNITUDE_BOUND)


# --- routing --------------------------------------------------------------


def test_routing_home_and_away_targets() -> None:
    delta = resolve_goal_deltas(
        [
            ("home_attack", 0.2),
            ("away_defense", 0.1),  # weaker away defense -> home scores more
            ("home_adv", 0.1),
            ("away_attack", 0.3),
            ("home_defense", 0.05),  # weaker home defense -> away scores more
        ]
    )
    assert delta.home_delta == pytest.approx(0.4)
    assert delta.away_delta == pytest.approx(0.35)


def test_disciplinary_targets_accumulate_separately() -> None:
    delta = resolve_goal_deltas([("cards_rate", 0.3), ("cards_rate", 0.1), ("pen_rate", 0.2)])
    assert delta.home_delta == 0.0
    assert delta.away_delta == 0.0
    assert delta.discipline == {"cards_rate": pytest.approx(0.4), "pen_rate": pytest.approx(0.2)}


def test_unknown_target_raises() -> None:
    with pytest.raises(ValueError, match="unknown adjustment target"):
        resolve_goal_deltas([("midfield_vibes", 0.2)])


# --- lambda floor ---------------------------------------------------------


def test_floor_keeps_lambda_positive_under_big_negative() -> None:
    # A low base rate plus the most negative allowed adjustment must still leave a
    # strictly positive Poisson mean.
    base_home, base_away = 0.3, 0.3
    delta = GoalAdjustment(home_delta=-MAGNITUDE_BOUND, away_delta=0.0, discipline={})
    lambda_home, mu_away = adjusted_expected_goals(base_home, base_away, delta)
    assert lambda_home == pytest.approx(LAMBDA_FLOOR)
    assert lambda_home > 0
    assert mu_away == pytest.approx(0.3)


def test_floor_applies_through_predict_for_a_weak_team() -> None:
    ratings = _ratings()
    # Most negative allowed nudge to the weak team's away attack; matrix must
    # still be a valid distribution (sums to ~1, no NaNs).
    adjusted = predict_adjusted(ratings, "strong", "weak", [("away_attack", -MAGNITUDE_BOUND)])
    total = adjusted.p_home + adjusted.p_draw + adjusted.p_away
    assert total == pytest.approx(1.0, abs=1e-9)
    assert adjusted.exp_away_goals > 0


# --- behaviour vs baseline -----------------------------------------------


def test_empty_adjustments_reproduce_baseline() -> None:
    ratings = _ratings()
    base = ratings.predict("strong", "weak")
    adjusted = predict_adjusted(ratings, "strong", "weak", [])
    assert adjusted.p_home == pytest.approx(base.p_home)
    assert adjusted.exp_home_goals == pytest.approx(base.exp_home_goals)


def test_positive_home_attack_raises_home_win_prob() -> None:
    ratings = _ratings()
    base = ratings.predict("strong", "weak")
    adjusted = predict_adjusted(ratings, "strong", "weak", [("home_attack", 0.3)])
    assert adjusted.p_home > base.p_home
    assert adjusted.exp_home_goals > base.exp_home_goals


def test_disciplinary_adjustment_leaves_result_unchanged() -> None:
    # A strict referee must not move the 1X2 distribution at all.
    ratings = _ratings()
    base = ratings.predict("strong", "weak")
    adjusted = predict_adjusted(ratings, "strong", "weak", [("cards_rate", 0.5)])
    assert adjusted.p_home == pytest.approx(base.p_home)
    assert adjusted.p_draw == pytest.approx(base.p_draw)
    assert adjusted.p_away == pytest.approx(base.p_away)
