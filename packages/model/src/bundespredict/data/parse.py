"""Parse football-data.co.uk Bundesliga (D1) season CSVs into typed rows.

Pure parsing only: no team-name canonicalization and no database. Team names
are returned as their raw football-data strings; canonicalization happens at
ingest time (so this module stays free of the alias map and trivially
testable). Rows without a final score (postponed/abandoned fixtures, or blank
trailing lines) are dropped here, which is what keeps null scores out of the
database downstream.
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# football-data uses 4-digit years in recent seasons; keep the 2-digit form as a
# fallback for older files.
_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y")
_SEASON_RE = re.compile(r"D1_(\w+)\.csv$")


@dataclass(frozen=True, slots=True)
class MatchRow:
    """One played Bundesliga match, with raw (un-canonicalized) team names."""

    season: str
    date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    ftr: str
    ht_home_goals: int | None
    ht_away_goals: int | None
    htr: str | None
    home_shots: int | None
    away_shots: int | None
    home_sot: int | None
    away_sot: int | None
    home_fouls: int | None
    away_fouls: int | None
    home_corners: int | None
    away_corners: int | None
    home_yellows: int | None
    away_yellows: int | None
    home_reds: int | None
    away_reds: int | None
    b365_home: float | None
    b365_draw: float | None
    b365_away: float | None
    avg_home: float | None
    avg_draw: float | None
    avg_away: float | None
    # Closing 1X2 odds (football-data "C" suffix) — the line just before kickoff.
    b365c_home: float | None
    b365c_draw: float | None
    b365c_away: float | None
    avgc_home: float | None
    avgc_draw: float | None
    avgc_away: float | None


def season_from_path(path: Path) -> str:
    """Extract the season code from a ``D1_<code>.csv`` filename (e.g. ``2324``)."""
    match = _SEASON_RE.search(path.name)
    if match is None:
        raise ValueError(f"cannot derive season from filename {path.name!r}")
    return match.group(1)


def _opt_str(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value or None


def _opt_int(raw: str | None) -> int | None:
    value = (raw or "").strip()
    return int(value) if value else None


def _opt_float(raw: str | None) -> float | None:
    value = (raw or "").strip()
    return float(value) if value else None


def _parse_date(raw: str) -> date:
    value = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()  # noqa: DTZ007 (naive date is intended)
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {value!r}")


def parse_match_csv(path: Path) -> list[MatchRow]:
    """Parse one season CSV into played matches; skip rows without a final score."""
    season = season_from_path(path)
    rows: list[MatchRow] = []
    skipped = 0

    # latin-1 never raises on football-data's encoding; the columns we read are
    # ASCII/numeric so byte-exact decoding of other columns doesn't matter.
    with path.open(encoding="latin-1", newline="") as fh:
        for record in csv.DictReader(fh):
            home = _opt_str(record.get("HomeTeam"))
            away = _opt_str(record.get("AwayTeam"))
            home_goals = _opt_int(record.get("FTHG"))
            away_goals = _opt_int(record.get("FTAG"))
            ftr = _opt_str(record.get("FTR"))

            if home is None or away is None or home_goals is None or away_goals is None:
                skipped += 1
                continue
            if ftr not in {"H", "D", "A"}:
                skipped += 1
                continue

            rows.append(
                MatchRow(
                    season=season,
                    date=_parse_date(record["Date"]),
                    home_team=home,
                    away_team=away,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    ftr=ftr,
                    ht_home_goals=_opt_int(record.get("HTHG")),
                    ht_away_goals=_opt_int(record.get("HTAG")),
                    htr=_opt_str(record.get("HTR")),
                    home_shots=_opt_int(record.get("HS")),
                    away_shots=_opt_int(record.get("AS")),
                    home_sot=_opt_int(record.get("HST")),
                    away_sot=_opt_int(record.get("AST")),
                    home_fouls=_opt_int(record.get("HF")),
                    away_fouls=_opt_int(record.get("AF")),
                    home_corners=_opt_int(record.get("HC")),
                    away_corners=_opt_int(record.get("AC")),
                    home_yellows=_opt_int(record.get("HY")),
                    away_yellows=_opt_int(record.get("AY")),
                    home_reds=_opt_int(record.get("HR")),
                    away_reds=_opt_int(record.get("AR")),
                    b365_home=_opt_float(record.get("B365H")),
                    b365_draw=_opt_float(record.get("B365D")),
                    b365_away=_opt_float(record.get("B365A")),
                    avg_home=_opt_float(record.get("AvgH")),
                    avg_draw=_opt_float(record.get("AvgD")),
                    avg_away=_opt_float(record.get("AvgA")),
                    b365c_home=_opt_float(record.get("B365CH")),
                    b365c_draw=_opt_float(record.get("B365CD")),
                    b365c_away=_opt_float(record.get("B365CA")),
                    avgc_home=_opt_float(record.get("AvgCH")),
                    avgc_draw=_opt_float(record.get("AvgCD")),
                    avgc_away=_opt_float(record.get("AvgCA")),
                )
            )

    logger.info("parsed %s: %d played, %d skipped", path.name, len(rows), skipped)
    return rows
