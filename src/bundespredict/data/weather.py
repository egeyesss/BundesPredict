"""Match-day weather grounding for the agent (Open-Meteo, keyless).

Weather is agent-layer *grounding*, never a model input. The knowledge base's
``weather_wind`` / ``weather_rain`` / ``weather_heat`` ranges still size any
adjustment; this module only lets the agent *check* a forecast instead of
trusting a user's "it'll be stormy". The model never sees weather — same
epistemic status as ``lookup_player``.

The pieces are separable like the fixtures module: :data:`STADIUMS` and
:func:`stadium_for` are pure lookups, :func:`parse_forecast` is pure (payload in,
typed report out — testable from a recorded response), and :func:`fetch_forecast`
is the only network call. :func:`default_weather_provider` wires fetch to parse
and fails soft — a blocked or out-of-range forecast returns ``None`` rather than
breaking a prediction, so the app degrades to the user's stated conditions.

Open-Meteo is keyless and only forecasts ~16 days ahead, which suits the use
case: grounding the weather for an imminent fixture. A date outside that window
yields ``None`` and the agent says so honestly.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

_API_URL = "https://api.open-meteo.com/v1/forecast"
# Open-Meteo daily fields we ask for; the order is irrelevant, we read by key.
_DAILY_FIELDS = "temperature_2m_max,precipitation_sum,wind_speed_10m_max"
# German local time so a "daily max" lines up with the actual match day.
_TIMEZONE = "Europe/Berlin"


@dataclass(frozen=True)
class Stadium:
    """A club's home venue: the coordinates a forecast is fetched for."""

    team: str  # canonical team name
    city: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WeatherReport:
    """The match-day forecast the tool reports, all raw measurements.

    Thresholds ("is this strong wind?") are the agent's judgement via the KB,
    not baked in here — the report just states the numbers.
    """

    team: str
    city: str
    date: date
    temperature_c: float  # daily max, deg C
    wind_kmh: float  # daily max gust-free wind speed at 10 m
    precip_mm: float  # daily precipitation total


# Home stadium coordinates for every club in the results history. Static
# reference data (a stadium doesn't move); kept as a typed dict rather than a
# JSON asset so it needs no packaging and stays unit-checkable.
STADIUMS: dict[str, Stadium] = {
    "1.FC Heidenheim 1846": Stadium("1.FC Heidenheim 1846", "Heidenheim", 48.6686, 10.1533),
    "1.FC Köln": Stadium("1.FC Köln", "Cologne", 50.9333, 6.8750),
    "1.FC Union Berlin": Stadium("1.FC Union Berlin", "Berlin", 52.4573, 13.5681),
    "1.FSV Mainz 05": Stadium("1.FSV Mainz 05", "Mainz", 49.9841, 8.2244),
    "Arminia Bielefeld": Stadium("Arminia Bielefeld", "Bielefeld", 52.0313, 8.5164),
    "Bayer 04 Leverkusen": Stadium("Bayer 04 Leverkusen", "Leverkusen", 51.0382, 7.0022),
    "Bayern Munich": Stadium("Bayern Munich", "Munich", 48.2188, 11.6247),
    "Borussia Dortmund": Stadium("Borussia Dortmund", "Dortmund", 51.4926, 7.4518),
    "Borussia Mönchengladbach": Stadium(
        "Borussia Mönchengladbach", "Mönchengladbach", 51.1746, 6.3856
    ),
    "Eintracht Frankfurt": Stadium("Eintracht Frankfurt", "Frankfurt", 50.0686, 8.6455),
    "FC Augsburg": Stadium("FC Augsburg", "Augsburg", 48.3231, 10.8861),
    "FC Schalke 04": Stadium("FC Schalke 04", "Gelsenkirchen", 51.5546, 7.0678),
    "FC St. Pauli": Stadium("FC St. Pauli", "Hamburg", 53.5546, 9.9678),
    "Fortuna Düsseldorf": Stadium("Fortuna Düsseldorf", "Düsseldorf", 51.2612, 6.7333),
    "Hamburger SV": Stadium("Hamburger SV", "Hamburg", 53.5872, 9.8983),
    "Hertha BSC": Stadium("Hertha BSC", "Berlin", 52.5147, 13.2395),
    "Holstein Kiel": Stadium("Holstein Kiel", "Kiel", 54.3492, 10.1247),
    "RB Leipzig": Stadium("RB Leipzig", "Leipzig", 51.3459, 12.3483),
    "SC Freiburg": Stadium("SC Freiburg", "Freiburg", 48.0217, 7.8297),
    "SC Paderborn 07": Stadium("SC Paderborn 07", "Paderborn", 51.7181, 8.7069),
    "SpVgg Greuther Fürth": Stadium("SpVgg Greuther Fürth", "Fürth", 49.4900, 10.9906),
    "SV 07 Elversberg": Stadium("SV 07 Elversberg", "Elversberg", 49.2497, 7.1350),
    "SV Darmstadt 98": Stadium("SV Darmstadt 98", "Darmstadt", 49.8558, 8.6725),
    "SV Werder Bremen": Stadium("SV Werder Bremen", "Bremen", 53.0664, 8.8378),
    "TSG 1899 Hoffenheim": Stadium("TSG 1899 Hoffenheim", "Sinsheim", 49.2386, 8.8875),
    "VfB Stuttgart": Stadium("VfB Stuttgart", "Stuttgart", 48.7922, 9.2320),
    "VfL Bochum": Stadium("VfL Bochum", "Bochum", 51.4897, 7.2367),
    "VfL Wolfsburg": Stadium("VfL Wolfsburg", "Wolfsburg", 52.4319, 10.8039),
}


def stadium_for(team: str) -> Stadium | None:
    """The home stadium for a canonical team name, or ``None`` if unmapped."""
    return STADIUMS.get(team)


def fetch_forecast(latitude: float, longitude: float, target: date) -> dict[str, Any]:
    """Fetch the daily forecast for one venue and day from Open-Meteo.

    Restricting ``start_date == end_date == target`` keeps the payload to the
    single day we care about. Raises on a network/HTTP error; the provider above
    turns that into a soft ``None``.
    """
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": _DAILY_FIELDS,
            "timezone": _TIMEZONE,
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
        }
    )
    with urllib.request.urlopen(f"{_API_URL}?{query}", timeout=15) as resp:
        return dict(json.loads(resp.read().decode("utf-8")))


def parse_forecast(
    payload: dict[str, Any], target: date, *, team: str, city: str
) -> WeatherReport | None:
    """Pull the row for ``target`` out of an Open-Meteo daily payload.

    Returns ``None`` when the day isn't present (the request fell outside the
    forecast window, so Open-Meteo returned other days or nothing) — the caller
    reads that as "no forecast available", never as calm weather.
    """
    daily = payload.get("daily") or {}
    days = daily.get("time") or []
    iso = target.isoformat()
    if iso not in days:
        return None
    i = days.index(iso)

    def _at(field: str) -> float | None:
        values = daily.get(field) or []
        if i >= len(values) or values[i] is None:
            return None
        return float(values[i])

    temp = _at("temperature_2m_max")
    wind = _at("wind_speed_10m_max")
    precip = _at("precipitation_sum")
    if temp is None or wind is None or precip is None:
        return None
    return WeatherReport(
        team=team,
        city=city,
        date=target,
        temperature_c=temp,
        wind_kmh=wind,
        precip_mm=precip,
    )


# A provider maps (canonical team, match day) to a forecast or None. The default
# hits the network; tests inject a fake so CI makes no request.
WeatherProvider = Callable[[str, date], "WeatherReport | None"]


def default_weather_provider(team: str, target: date) -> WeatherReport | None:
    """Fetch-and-parse provider that fails soft.

    Any missing venue, out-of-window date, or network hiccup becomes ``None`` so
    a forecast problem degrades gracefully to the user's stated conditions and
    never breaks a prediction.
    """
    stadium = stadium_for(team)
    if stadium is None:
        return None
    try:
        payload = fetch_forecast(stadium.latitude, stadium.longitude, target)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    return parse_forecast(payload, target, team=stadium.team, city=stadium.city)
