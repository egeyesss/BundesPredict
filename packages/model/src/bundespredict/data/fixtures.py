"""Upcoming-fixture schedule: OpenLigaDB fetch and parse.

Results history comes from football-data CSVs, but those only exist after a
match is played — "who does Dortmund play next?" needs the schedule. OpenLigaDB
(https://api.openligadb.de) publishes the Bundesliga calendar, including future
matchdays, keyless.

:func:`parse_fixtures` is pure (JSON in, typed rows out, testable from a recorded
payload) and :func:`fetch_season_json` is the only network call. Storing the rows
is the caller's job.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .seasons import season_code

_API_URL = "https://api.openligadb.de/getmatchdata/bl1/{year}"


@dataclass(frozen=True)
class FixtureRow:
    """One scheduled match parsed from the source, teams still source-spelled."""

    season: str  # e.g. "2627"
    matchday: int
    kickoff_utc: datetime  # naive UTC
    home: str
    away: str


@dataclass(frozen=True)
class UpcomingFixture:
    """One scheduled match as the agent reports it, teams canonical."""

    kickoff_utc: datetime
    matchday: int
    season: str
    home: str
    away: str


def fetch_season_json(start_year: int) -> list[dict[str, Any]]:
    """Download one season's full match list (played and scheduled)."""
    with urllib.request.urlopen(_API_URL.format(year=start_year), timeout=30) as resp:
        return list(json.loads(resp.read().decode("utf-8")))


def parse_fixtures(payload: list[dict[str, Any]], start_year: int) -> list[FixtureRow]:
    """Extract the *unplayed* matches from an OpenLigaDB season payload.

    Played matches are dropped — results are football-data's job — and so is
    anything without a matchday or kickoff (defensive; the API has been known to
    carry placeholder entries early in a season).
    """
    rows: list[FixtureRow] = []
    for entry in payload:
        if entry.get("matchIsFinished"):
            continue
        group = entry.get("group") or {}
        matchday = group.get("groupOrderID")
        kickoff_raw = entry.get("matchDateTimeUTC")
        team1 = (entry.get("team1") or {}).get("teamName")
        team2 = (entry.get("team2") or {}).get("teamName")
        if not (matchday and kickoff_raw and team1 and team2):
            continue
        kickoff = datetime.fromisoformat(kickoff_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        rows.append(
            FixtureRow(
                season=season_code(start_year),
                matchday=int(matchday),
                kickoff_utc=kickoff,
                home=str(team1),
                away=str(team2),
            )
        )
    return rows
