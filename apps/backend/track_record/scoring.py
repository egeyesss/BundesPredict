"""Scoring of 1X2 forecasts against results, on top of the model package's pure metrics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from bundespredict.eval.metrics import multiclass_log_loss, rps_per_match

# Long-run Bundesliga split of home, draw and away results; the naive forecast to beat.
BASE_RATE: tuple[float, float, float] = (0.44, 0.25, 0.31)

CALIBRATION_BINS = 10
HOME, DRAW, AWAY = 0, 1, 2


@dataclass(frozen=True)
class Forecast:
    """Probabilities of (home, draw, away) and the index of what actually happened."""

    probs: tuple[float, float, float]
    outcome: int


@dataclass(frozen=True)
class MatchScore:
    rps: float
    log_loss: float
    hit: bool


@dataclass(frozen=True)
class Summary:
    n_fixtures: int
    rps: float
    log_loss: float
    hit_rate: float


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    predicted_mean: float
    observed_rate: float
    count: int


def outcome_index(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return HOME
    if home_goals < away_goals:
        return AWAY
    return DRAW


def top_pick(probs: tuple[float, float, float]) -> int:
    """The most likely outcome; a tie goes to a team over the draw, like the odds display."""
    return max((HOME, AWAY, DRAW), key=lambda index: probs[index])


def _arrays(forecasts: Sequence[Forecast]) -> tuple[np.ndarray, np.ndarray]:
    probs = np.array([f.probs for f in forecasts], dtype=np.float64)
    outcomes = np.array([f.outcome for f in forecasts], dtype=np.intp)
    return probs, outcomes


def score_forecast(forecast: Forecast) -> MatchScore:
    probs, outcomes = _arrays([forecast])
    return MatchScore(
        rps=float(rps_per_match(probs, outcomes)[0]),
        log_loss=multiclass_log_loss(probs, outcomes),
        hit=top_pick(forecast.probs) == forecast.outcome,
    )


def summarize(forecasts: Sequence[Forecast]) -> Summary | None:
    if not forecasts:
        return None
    scores = [score_forecast(f) for f in forecasts]
    n = len(scores)
    return Summary(
        n_fixtures=n,
        rps=sum(s.rps for s in scores) / n,
        log_loss=sum(s.log_loss for s in scores) / n,
        hit_rate=sum(s.hit for s in scores) / n,
    )


def calibration_bins(forecasts: Sequence[Forecast]) -> list[CalibrationBin]:
    """Home, draw and away probabilities pooled into tenth-wide bins, empty bins dropped."""
    predicted: list[float] = []
    happened: list[float] = []
    for forecast in forecasts:
        for index, probability in enumerate(forecast.probs):
            predicted.append(probability)
            happened.append(1.0 if index == forecast.outcome else 0.0)
    if not predicted:
        return []

    predicted_array = np.array(predicted)
    happened_array = np.array(happened)
    # A probability of exactly 1.0 belongs in the top bin rather than a bin of its own.
    bin_index = np.minimum((predicted_array * CALIBRATION_BINS).astype(int), CALIBRATION_BINS - 1)
    width = 1.0 / CALIBRATION_BINS
    bins = []
    for index in range(CALIBRATION_BINS):
        in_bin = bin_index == index
        count = int(in_bin.sum())
        if count == 0:
            continue
        bins.append(
            CalibrationBin(
                lower=index * width,
                upper=(index + 1) * width,
                predicted_mean=float(predicted_array[in_bin].mean()),
                observed_rate=float(happened_array[in_bin].mean()),
                count=count,
            )
        )
    return bins
