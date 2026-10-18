"""Understat per-match expected goals: parse the cache into typed rows.

Understat is the pre-match xG feature's data source. The ``scrape_understat`` command
caches each season's ``datesData`` array (raw Understat JSON) to ``data/understat_cache/``;
this module is the pure parser. Attaching each match's xG to the stored match is the
caller's job. xG is *joined onto* the results history rather than owning rows:
football-data remains the authority on which matches exist and their scores.

The rows carry **final-match** xG. That is safe only because the model never reads it
directly: the training service turns it into a rolling average over matches strictly
before kickoff. Using it un-rolled would be leakage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .team_aliases import UNDERSTAT_ALIASES, canonical_team_name


@dataclass(frozen=True)
class UnderstatMatch:
    """One played match's expected goals, teams already canonicalized."""

    season: str  # e.g. "2324"
    understat_id: str
    date: date
    home: str
    away: str
    home_xg: float
    away_xg: float


def parse_understat_season(payload: list[dict[str, Any]], season: str) -> list[UnderstatMatch]:
    """Extract played matches (with xG) from one season's ``datesData`` array.

    Unplayed fixtures (``isResult`` false — the rest of the current season) carry
    no xG and are dropped. Team names canonicalize up front, so an unmapped club
    raises loudly here rather than silently failing to join later.
    """
    rows: list[UnderstatMatch] = []
    for entry in payload:
        if not entry.get("isResult"):
            continue
        home = canonical_team_name(entry["h"]["title"], source_aliases=UNDERSTAT_ALIASES)
        away = canonical_team_name(entry["a"]["title"], source_aliases=UNDERSTAT_ALIASES)
        played = datetime.strptime(entry["datetime"], "%Y-%m-%d %H:%M:%S").date()
        rows.append(
            UnderstatMatch(
                season=season,
                understat_id=str(entry["id"]),
                date=played,
                home=home,
                away=away,
                home_xg=float(entry["xG"]["h"]),
                away_xg=float(entry["xG"]["a"]),
            )
        )
    return rows


def _season_from_filename(path: Path) -> str:
    """``bundesliga_2324.json`` -> ``"2324"``."""
    return path.stem.split("_")[-1]


def load_cache(cache_dir: Path) -> dict[str, list[UnderstatMatch]]:
    """Parse every ``bundesliga_*.json`` in the cache into rows keyed by season."""
    seasons: dict[str, list[UnderstatMatch]] = {}
    for path in sorted(cache_dir.glob("bundesliga_*.json")):
        season = _season_from_filename(path)
        payload = list(json.loads(path.read_text()))
        seasons[season] = parse_understat_season(payload, season)
    return seasons
