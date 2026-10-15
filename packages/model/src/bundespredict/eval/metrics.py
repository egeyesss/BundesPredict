"""Probabilistic-forecast metrics for 1X2 predictions.

Pure and array-only: every function takes an ``(N, 3)`` probability matrix with
columns ordered ``[home, draw, away]`` and an ``(N,)`` integer outcome array
(``0 = home, 1 = draw, 2 = away``), and returns a plain float (or a small
dataclass). No DB, no plotting — the backtest assembles the arrays, this scores
them, and a separate reporting step draws the picture.

The headline metric is the **Ranked Probability Score**. H/D/A is *ordinal* (a
draw sits between a home and an away win), so being confidently wrong by two
steps (predicting a home blowout when the away side wins) should cost more than
missing by one. RPS captures that through cumulative distributions; plain Brier
and log-loss, which treat the three outcomes as unordered, are reported
alongside as the familiar secondary numbers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

# Column / class order used everywhere downstream. Home < Draw < Away is the
# ordinal scale RPS reads cumulatively.
RESULTS: tuple[str, str, str] = ("H", "D", "A")
_RESULT_INDEX = {r: i for i, r in enumerate(RESULTS)}


def encode_outcomes(ftrs: Sequence[str]) -> NDArray[np.intp]:
    """Map full-time-result letters (``H``/``D``/``A``) to class indices 0/1/2."""
    try:
        return np.array([_RESULT_INDEX[f] for f in ftrs], dtype=np.intp)
    except KeyError as exc:  # pragma: no cover - guards against dirty data
        raise ValueError(f"unrecognized result letter: {exc.args[0]!r}") from exc


def _validate(probs: NDArray[np.float64], outcomes: NDArray[np.intp]) -> None:
    if probs.ndim != 2 or probs.shape[1] != 3:
        raise ValueError(f"probs must be (N, 3), got {probs.shape}")
    if outcomes.shape != (probs.shape[0],):
        raise ValueError(f"outcomes must be ({probs.shape[0]},), got {outcomes.shape}")
    if probs.size and (outcomes.min() < 0 or outcomes.max() > 2):
        raise ValueError("outcomes must be in {0, 1, 2}")


def _one_hot(outcomes: NDArray[np.intp]) -> NDArray[np.float64]:
    oh = np.zeros((outcomes.shape[0], 3), dtype=np.float64)
    oh[np.arange(outcomes.shape[0]), outcomes] = 1.0
    return oh


def rps_per_match(probs: NDArray[np.float64], outcomes: NDArray[np.intp]) -> NDArray[np.float64]:
    """Per-match Ranked Probability Score (lower is better, 0 = perfect).

    For three ordered categories::

        RPS = 1/2 * [ (C1_p - C1_e)^2 + (C2_p - C2_e)^2 ]

    where ``C*`` are cumulative probabilities/indicators. The final cumulative
    term is always 1 for both forecast and outcome, so it drops out and only the
    first two boundaries contribute.
    """
    _validate(probs, outcomes)
    cum_p = np.cumsum(probs, axis=1)[:, :2]
    cum_e = np.cumsum(_one_hot(outcomes), axis=1)[:, :2]
    return np.asarray(np.sum((cum_p - cum_e) ** 2, axis=1) / 2.0, dtype=np.float64)


def ranked_probability_score(probs: NDArray[np.float64], outcomes: NDArray[np.intp]) -> float:
    """Mean RPS across matches — the primary accuracy metric."""
    return float(np.mean(rps_per_match(probs, outcomes)))


def multiclass_log_loss(
    probs: NDArray[np.float64], outcomes: NDArray[np.intp], *, eps: float = 1e-15
) -> float:
    """Mean negative log-likelihood of the realized outcomes (lower is better)."""
    _validate(probs, outcomes)
    picked = probs[np.arange(outcomes.shape[0]), outcomes]
    return float(-np.mean(np.log(np.clip(picked, eps, 1.0))))


def multiclass_brier(probs: NDArray[np.float64], outcomes: NDArray[np.intp]) -> float:
    """Mean multiclass Brier score: mean squared error vs the one-hot outcome.

    Summed over the three classes (range 0..2), the unordered counterpart to
    RPS — reported as a secondary, order-blind sanity number.
    """
    _validate(probs, outcomes)
    return float(np.mean(np.sum((probs - _one_hot(outcomes)) ** 2, axis=1)))


@dataclass(frozen=True)
class ReliabilityCurve:
    """Binned reliability data for a calibration diagram, plus its ECE.

    Built *classwise*: every (predicted probability, did-it-happen) pair across
    all three outcomes is pooled, then bucketed by predicted probability. So a
    bin centered at 0.30 answers "of all the times the model said ~30% for some
    outcome, how often did that outcome occur?" — exactly the calibration
    question for a three-way market. Empty bins are dropped from the arrays.
    """

    bin_mean_pred: NDArray[np.float64]  # mean predicted prob in each (non-empty) bin
    bin_frac_pos: NDArray[np.float64]  # observed frequency in each bin
    bin_count: NDArray[np.intp]  # number of pooled points in each bin
    ece: float  # count-weighted mean |frac_pos - mean_pred|


def reliability_curve(
    probs: NDArray[np.float64], outcomes: NDArray[np.intp], *, n_bins: int = 10
) -> ReliabilityCurve:
    """Pool all classwise (pred, hit) pairs into ``n_bins`` and summarize them."""
    _validate(probs, outcomes)
    pred = probs.ravel()
    hit = _one_hot(outcomes).ravel()

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # digitize -> bin index in 1..n_bins; shift to 0..n_bins-1 and clamp the 1.0 edge.
    bin_idx = np.clip(np.digitize(pred, edges) - 1, 0, n_bins - 1)

    mean_pred: list[float] = []
    frac_pos: list[float] = []
    counts: list[int] = []
    ece = 0.0
    total = pred.shape[0]
    for b in range(n_bins):
        mask = bin_idx == b
        count = int(mask.sum())
        if count == 0:
            continue
        mp = float(pred[mask].mean())
        fp = float(hit[mask].mean())
        mean_pred.append(mp)
        frac_pos.append(fp)
        counts.append(count)
        ece += (count / total) * abs(fp - mp)

    return ReliabilityCurve(
        bin_mean_pred=np.array(mean_pred, dtype=np.float64),
        bin_frac_pos=np.array(frac_pos, dtype=np.float64),
        bin_count=np.array(counts, dtype=np.intp),
        ece=ece,
    )


def expected_calibration_error(
    probs: NDArray[np.float64], outcomes: NDArray[np.intp], *, n_bins: int = 10
) -> float:
    """Classwise Expected Calibration Error (convenience over the full curve)."""
    return reliability_curve(probs, outcomes, n_bins=n_bins).ece


@dataclass(frozen=True)
class ForecastScores:
    """The four headline numbers for one set of forecasts against one outcome set."""

    n: int
    rps: float
    log_loss: float
    brier: float
    ece: float


def score_forecast(
    probs: NDArray[np.float64], outcomes: NDArray[np.intp], *, n_bins: int = 10
) -> ForecastScores:
    """Compute RPS, log-loss, Brier, and ECE in one pass — the reporting summary."""
    return ForecastScores(
        n=int(probs.shape[0]),
        rps=ranked_probability_score(probs, outcomes),
        log_loss=multiclass_log_loss(probs, outcomes),
        brier=multiclass_brier(probs, outcomes),
        ece=expected_calibration_error(probs, outcomes, n_bins=n_bins),
    )
