"""Tests for the weather grounding layer: stadium lookup + forecast parsing.

Pure, no network — the parser runs against a recorded Open-Meteo response so the
committed fixture pins the real payload shape.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from bundespredict.data.weather import STADIUMS, parse_forecast, stadium_for

_FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_forecast.json"


def _payload() -> dict[str, Any]:
    return dict(json.loads(_FIXTURE.read_text()))


def test_stadium_lookup_known_and_unknown() -> None:
    dortmund = stadium_for("Borussia Dortmund")
    assert dortmund is not None
    assert dortmund.city == "Dortmund"
    assert 51.0 < dortmund.latitude < 52.0
    assert stadium_for("Atlantis FC") is None


def test_every_stadium_is_keyed_by_its_own_team() -> None:
    # Guards a copy-paste slip in the table: the dict key must equal the row's team.
    for name, stadium in STADIUMS.items():
        assert stadium.team == name


def test_parse_forecast_picks_the_matching_day() -> None:
    report = parse_forecast(_payload(), date(2026, 7, 8), team="Borussia Dortmund", city="Dortmund")
    assert report is not None
    assert report.date == date(2026, 7, 8)
    assert report.temperature_c == 23.4
    assert report.wind_kmh == 13.0
    assert report.precip_mm == 0.1


def test_parse_forecast_returns_none_for_a_day_out_of_window() -> None:
    # A date the forecast doesn't cover reads as "no forecast", not calm weather.
    assert parse_forecast(_payload(), date(2026, 9, 1), team="X", city="Y") is None


def test_parse_forecast_handles_empty_payload() -> None:
    assert parse_forecast({}, date(2026, 7, 7), team="X", city="Y") is None
