from __future__ import annotations

import re
from pathlib import Path

import pytest

from track_record.backtest_summary import BACKTEST

REPORT = Path(__file__).resolve().parents[4] / "reports" / "backtest_report.md"

ROW = re.compile(
    r"^\| (?P<name>[^|]+) \| (?P<n>\d+) \| (?P<rps>[\d.]+) \| (?P<log_loss>[\d.]+) \|", re.MULTILINE
)


def overall_table() -> dict[str, tuple[int, float, float]]:
    """The first score table in the report: every predicted season together."""
    text = REPORT.read_text()
    section = text.split("## Overall", 1)[1].split("## Holdout", 1)[0]
    return {
        match["name"].strip(): (int(match["n"]), float(match["rps"]), float(match["log_loss"]))
        for match in ROW.finditer(section)
    }


@pytest.fixture(scope="module")
def table() -> dict[str, tuple[int, float, float]]:
    return overall_table()


def test_model_numbers_match_the_checked_in_report(
    table: dict[str, tuple[int, float, float]],
) -> None:
    n, rps, log_loss = table["model (calibrated)"]

    assert BACKTEST.n_fixtures == n == 1827
    assert BACKTEST.model_rps == rps == 0.2045
    assert BACKTEST.model_log_loss == log_loss


def test_closing_market_numbers_match_the_report(
    table: dict[str, tuple[int, float, float]],
) -> None:
    _, rps, log_loss = table["market (close, de-vig)"]

    assert BACKTEST.market_rps == rps == 0.1967
    assert BACKTEST.market_log_loss == log_loss


def test_every_forecaster_matches_its_report_row(
    table: dict[str, tuple[int, float, float]],
) -> None:
    report_rows = {
        "market_close": "market (close, de-vig)",
        "market_open": "market (open, de-vig)",
        "model_calibrated": "model (calibrated)",
        "model_uncalibrated": "model (uncalibrated)",
        "model_xg": "model + pre-match xG (uncal)",
    }

    for forecaster in BACKTEST.forecasters:
        _, rps, log_loss = table[report_rows[forecaster.key]]
        assert (forecaster.rps, forecaster.log_loss) == (rps, log_loss)
    assert {f.key for f in BACKTEST.forecasters} == set(report_rows)


def test_exactly_one_forecaster_is_the_serving_model() -> None:
    serving = [f for f in BACKTEST.forecasters if f.serving]

    assert [f.key for f in serving] == ["model_calibrated"]
