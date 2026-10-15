"""Probability calibration by temperature scaling.

Raw Dixon-Coles probabilities are usually a touch overconfident: the model says
70% more often than 70% actually happens. Temperature scaling fixes that with a
single parameter ``T`` — it divides the logits by ``T`` before re-softmaxing, so
``T > 1`` softens every forecast toward uniform and ``T < 1`` sharpens it. One
parameter is the right amount of flexibility for a holdout of only a few hundred
matches; per-class isotonic regression is the more-data alternative and overfits
the bins here (see PROJECT_PLAN §6.4).

Working through the softmax keeps the three probabilities summing to 1 by
construction, so there's no separate "calibrate then renormalize" step to get
wrong. At ``T = 1`` the transform is the identity. Pure: probabilities in,
probabilities out; the fit minimizes holdout log-loss with no DB or plotting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize_scalar

_EPS = 1e-12


def _scale(probs: NDArray[np.float64], temperature: float) -> NDArray[np.float64]:
    """Divide logits by ``temperature`` and re-softmax (stable, rows sum to 1)."""
    logits = np.log(np.clip(probs, _EPS, 1.0)) / temperature
    logits -= logits.max(axis=1, keepdims=True)  # stabilize before exp
    exp = np.exp(logits)
    return np.asarray(exp / exp.sum(axis=1, keepdims=True), dtype=np.float64)


@dataclass(frozen=True)
class TemperatureScaler:
    """A fitted calibrator. Apply it to any model probabilities with ``transform``."""

    temperature: float

    def transform(self, probs: NDArray[np.float64]) -> NDArray[np.float64]:
        if probs.ndim != 2 or probs.shape[1] != 3:
            raise ValueError(f"probs must be (N, 3), got {probs.shape}")
        return _scale(probs, self.temperature)


def fit_temperature_scaler(
    probs: NDArray[np.float64],
    outcomes: NDArray[np.intp],
    *,
    bounds: tuple[float, float] = (0.05, 20.0),
) -> TemperatureScaler:
    """Pick the temperature that minimizes log-loss on a holdout.

    ``probs`` are the model's uncalibrated ``(N, 3)`` forecasts and ``outcomes``
    the realized class indices (0/1/2). The search is one-dimensional and convex
    in practice, so a bounded scalar minimizer is plenty.
    """
    if probs.ndim != 2 or probs.shape[1] != 3:
        raise ValueError(f"probs must be (N, 3), got {probs.shape}")
    if outcomes.shape != (probs.shape[0],):
        raise ValueError("outcomes must align with probs rows")

    rows = np.arange(outcomes.shape[0])

    def neg_log_likelihood(temperature: float) -> float:
        scaled = _scale(probs, temperature)
        picked = scaled[rows, outcomes]
        return float(-np.mean(np.log(np.clip(picked, _EPS, 1.0))))

    result = minimize_scalar(neg_log_likelihood, bounds=bounds, method="bounded")
    return TemperatureScaler(temperature=float(result.x))
