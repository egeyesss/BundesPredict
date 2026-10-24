"""Headline numbers of the walk-forward backtest, copied from reports/backtest_report.md.

A test compares every figure with the report, so the two cannot drift apart unnoticed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Forecaster:
    key: str
    label: str
    kind: str
    rps: float
    log_loss: float
    serving: bool = False


@dataclass(frozen=True)
class BacktestSummary:
    label: str
    n_fixtures: int
    model_rps: float
    model_log_loss: float
    market_rps: float
    market_log_loss: float
    calibration_error: float
    forecasters: tuple[Forecaster, ...]


BACKTEST = BacktestSummary(
    label="Backtest, 5 seasons",
    n_fixtures=1827,
    model_rps=0.2045,
    model_log_loss=1.0010,
    market_rps=0.1967,
    market_log_loss=0.9744,
    calibration_error=0.0105,
    forecasters=(
        Forecaster("market_close", "Closing market", "market", 0.1967, 0.9744),
        Forecaster("market_open", "Opening market", "market", 0.1976, 0.9775),
        Forecaster("model_calibrated", "Model (calibrated)", "model", 0.2045, 1.0010, True),
        Forecaster("model_uncalibrated", "Model (uncalibrated)", "model", 0.2046, 1.0019),
        Forecaster("model_xg", "Model + pre-match xG", "model", 0.2069, 1.0116),
    ),
)
