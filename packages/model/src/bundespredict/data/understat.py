"""Understat per-match expected goals: parse the cache, backfill ``matches``.

Understat is the pre-match xG feature's data source. ``scripts/scrape_understat``
caches each season's ``datesData`` array (raw Understat JSON) to
``data/understat_cache/``; this module is the pure parser plus the DB writer that
attaches each match's final xG to the existing ``matches`` row.

The split mirrors the other data sources: :func:`parse_understat_season` is pure
(JSON in, typed rows out — testable from a committed fixture), and
:func:`ingest_understat` is the only DB writer. xG is *joined onto* the results
history rather than owning rows: football-data remains the authority on which
matches exist and their scores, and Understat only fills the two xG columns. A
row that doesn't match an existing fixture is counted and skipped, never
inserted — a mismatch is a data problem to surface, not a new match.

These stored values are **final-match** xG. They are safe only because the model
never reads them directly: the loader turns them into a rolling average over
matches strictly before kickoff. Storing the raw value here is not leakage;
using it un-rolled would be.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Match, Team, TeamAlias
from .team_aliases import UNDERSTAT_ALIASES, canonical_team_name

logger = logging.getLogger(__name__)

SOURCE = "understat"


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


@dataclass(frozen=True)
class UnderstatIngestStats:
    """What one ingest run touched, for a loud, auditable summary."""

    seasons: int
    parsed: int
    matched: int
    unmatched: int


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


def _team_ids_by_name(session: Session) -> dict[str, int]:
    """Canonical name -> team id, including source aliases for safety."""
    by_name = {name: tid for tid, name in session.execute(select(Team.id, Team.name))}
    # Understat spellings resolve to canonical names before lookup, but map any
    # alias rows too so a name that only exists as an alias still resolves.
    for alias, tid in session.execute(
        select(TeamAlias.alias, TeamAlias.team_id).where(TeamAlias.source == SOURCE)
    ):
        by_name.setdefault(alias, tid)
    return by_name


def ingest_understat(
    session: Session, seasons: dict[str, list[UnderstatMatch]]
) -> UnderstatIngestStats:
    """Backfill ``matches.home_xg`` / ``away_xg`` from parsed Understat rows.

    Idempotent: it updates the two xG columns on the matching fixture and nothing
    else, so re-running only ever rewrites the same values. A row whose
    ``(season, home, away)`` has no fixture in ``matches`` is counted as unmatched
    and skipped (never inserted).
    """
    name_to_id = _team_ids_by_name(session)
    parsed = matched = unmatched = 0
    for rows in seasons.values():
        for row in rows:
            parsed += 1
            home_id = name_to_id.get(row.home)
            away_id = name_to_id.get(row.away)
            match = None
            if home_id is not None and away_id is not None:
                match = session.execute(
                    select(Match).where(
                        Match.season == row.season,
                        Match.home_id == home_id,
                        Match.away_id == away_id,
                    )
                ).scalar_one_or_none()
            if match is None:
                unmatched += 1
                logger.warning(
                    "understat row without a fixture: %s %s vs %s",
                    row.season,
                    row.home,
                    row.away,
                )
                continue
            match.home_xg = row.home_xg
            match.away_xg = row.away_xg
            matched += 1
    session.commit()
    return UnderstatIngestStats(
        seasons=len(seasons), parsed=parsed, matched=matched, unmatched=unmatched
    )
