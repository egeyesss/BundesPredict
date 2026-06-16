"""Tests for temperature-scaling calibration."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.eval.metrics import expected_calibration_error, multiclass_log_loss
from bundespredict.model.calibration import (
    TemperatureScaler,
    fit_temperature_scaler,
)


def test_temperature_one_is_identity() -> None:
    probs = np.array([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]])
    out = TemperatureScaler(1.0).transform(probs)
    assert out == pytest.approx(probs)


def test_higher_temperature_softens_toward_uniform() -> None:
    probs = np.array([[0.7, 0.2, 0.1]])
    softened = TemperatureScaler(2.0).transform(probs)[0]
    sharpened = TemperatureScaler(0.5).transform(probs)[0]
    # Softening pulls the peak down toward 1/3; sharpening pushes it up.
    assert softened[0] < probs[0, 0]
    assert sharpened[0] > probs[0, 0]
    assert softened.sum() == pytest.approx(1.0)


def test_fit_recovers_softening_temperature_and_improves_calibration() -> None:
    # Build an *overconfident* model: outcomes are drawn from gentle true probs,
    # but the model reports those probs sharpened (logits doubled). The fix is to
    # divide logits back by ~2, so the fitted temperature should land near 2.
    rng = np.random.default_rng(7)
    n = 3000
    true_probs = np.array([0.45, 0.27, 0.28])
    outcomes = rng.choice(3, size=n, p=true_probs).astype(np.intp)

    logits = np.log(true_probs)
    sharp = np.exp(2.0 * logits)
    model_probs = np.tile(sharp / sharp.sum(), (n, 1))

    scaler = fit_temperature_scaler(model_probs, outcomes)
    calibrated = scaler.transform(model_probs)

    assert scaler.temperature == pytest.approx(2.0, abs=0.3)
    assert multiclass_log_loss(calibrated, outcomes) <= multiclass_log_loss(model_probs, outcomes)
    assert expected_calibration_error(calibrated, outcomes) < expected_calibration_error(
        model_probs, outcomes
    )


def test_transform_rejects_bad_shape() -> None:
    with pytest.raises(ValueError, match=r"\(N, 3\)"):
        TemperatureScaler(1.0).transform(np.zeros((2, 2)))
