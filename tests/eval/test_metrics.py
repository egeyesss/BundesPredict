"""Metrics checked against hand-worked tiny examples."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.eval.metrics import (
    encode_outcomes,
    expected_calibration_error,
    multiclass_brier,
    multiclass_log_loss,
    ranked_probability_score,
    reliability_curve,
    rps_per_match,
)


def test_encode_outcomes() -> None:
    assert list(encode_outcomes(["H", "D", "A", "H"])) == [0, 1, 2, 0]
    with pytest.raises(ValueError, match="result letter"):
        encode_outcomes(["H", "X"])


def test_rps_perfect_forecast_is_zero() -> None:
    probs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    outcomes = np.array([0, 1, 2], dtype=np.intp)
    assert ranked_probability_score(probs, outcomes) == pytest.approx(0.0)


def test_rps_uniform_forecast() -> None:
    # Uniform [1/3,1/3,1/3], home win: 0.5*[(1/3-1)^2 + (2/3-1)^2] = 5/18.
    probs = np.array([[1 / 3, 1 / 3, 1 / 3]])
    assert rps_per_match(probs, np.array([0], dtype=np.intp))[0] == pytest.approx(5 / 18)


def test_rps_penalizes_distance_ordinally() -> None:
    # Certain home prediction. An away result (two steps) must cost more than a
    # draw result (one step) — this is the whole point of using RPS over Brier.
    probs = np.array([[1.0, 0.0, 0.0]])
    one_step = rps_per_match(probs, np.array([1], dtype=np.intp))[0]
    two_step = rps_per_match(probs, np.array([2], dtype=np.intp))[0]
    assert one_step == pytest.approx(0.5)
    assert two_step == pytest.approx(1.0)
    assert two_step > one_step


def test_log_loss_and_brier_hand_values() -> None:
    probs = np.array([[0.5, 0.3, 0.2]])
    outcomes = np.array([0], dtype=np.intp)
    assert multiclass_log_loss(probs, outcomes) == pytest.approx(-np.log(0.5))
    # (0.5-1)^2 + 0.3^2 + 0.2^2 = 0.38
    assert multiclass_brier(probs, outcomes) == pytest.approx(0.38)


def test_perfectly_calibrated_has_zero_ece() -> None:
    # Confident-and-correct: every classwise (pred, hit) pair sits at 0 or 1 and
    # matches, so there is no calibration gap.
    probs = np.tile([1.0, 0.0, 0.0], (20, 1))
    outcomes = np.zeros(20, dtype=np.intp)
    assert expected_calibration_error(probs, outcomes) == pytest.approx(0.0)


def test_overconfident_forecast_has_positive_ece() -> None:
    # Always claims 90% home but home wins only half the time -> a real gap.
    rng = np.random.default_rng(0)
    n = 400
    probs = np.tile([0.9, 0.05, 0.05], (n, 1))
    outcomes = np.where(rng.random(n) < 0.5, 0, 2).astype(np.intp)
    curve = reliability_curve(probs, outcomes)
    assert curve.ece > 0.1
    # Bin counts cover every pooled (N*3) point.
    assert int(curve.bin_count.sum()) == n * 3


def test_shape_validation() -> None:
    with pytest.raises(ValueError, match=r"\(N, 3\)"):
        ranked_probability_score(np.zeros((2, 2)), np.zeros(2, dtype=np.intp))
    with pytest.raises(ValueError, match="outcomes must be"):
        ranked_probability_score(np.zeros((2, 3)), np.zeros(3, dtype=np.intp))
