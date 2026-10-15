"""Match results: download football-data CSVs into the raw directory, ingest them as `Match` rows.

Ingest is idempotent: rows are compared with what is stored and only new or changed ones are
written, so a second run over the same files touches nothing. The CSVs never carry xG, so the
xG columns (filled by the Understat job) are left alone.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path

from django.db import transaction

from bundespredict.data.footballdata import fetch_season_csv
from bundespredict.data.parse import MatchRow, parse_match_csv
from football.models import Match

from .teams import ensure_teams

logger = logging.getLogger(__name__)

SOURCE = "football-data"

_NATURAL_KEY_FIELDS = frozenset({"season", "home_team", "away_team"})
_MUTABLE_FIELDS = tuple(f.name for f in fields(MatchRow) if f.name not in _NATURAL_KEY_FIELDS)

SeasonFetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class UpsertSummary:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def __add__(self, other: UpsertSummary) -> UpsertSummary:
        return UpsertSummary(
            self.created + other.created,
            self.updated + other.updated,
            self.unchanged + other.unchanged,
        )

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


def download_season(code: str, raw_dir: Path, *, fetch: SeasonFetcher | None = None) -> bool:
    """Fetch one season's CSV into `raw_dir`; returns whether the file changed on disk."""
    data = (fetch or fetch_season_csv)(code)
    path = raw_dir / f"D1_{code}.csv"
    if path.exists() and path.read_bytes() == data:
        return False
    raw_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def ingest_rows(rows: list[MatchRow]) -> UpsertSummary:
    """Upsert parsed rows on the natural key (season, home, away); one transaction."""
    if not rows:
        return UpsertSummary()
    with transaction.atomic():
        team_ids = ensure_teams(
            {r.home_team for r in rows} | {r.away_team for r in rows}, source=SOURCE
        )
        seasons = {r.season for r in rows}
        existing = {
            (m.season, m.home_id, m.away_id): m for m in Match.objects.filter(season__in=seasons)
        }

        to_create: list[Match] = []
        to_update: list[Match] = []
        unchanged = 0
        for row in rows:
            key = (row.season, team_ids[row.home_team], team_ids[row.away_team])
            values = {name: getattr(row, name) for name in _MUTABLE_FIELDS}
            current = existing.get(key)
            if current is None:
                to_create.append(Match(season=row.season, home_id=key[1], away_id=key[2], **values))
            elif any(getattr(current, name) != value for name, value in values.items()):
                for name, value in values.items():
                    setattr(current, name, value)
                to_update.append(current)
            else:
                unchanged += 1

        Match.objects.bulk_create(to_create)
        Match.objects.bulk_update(to_update, list(_MUTABLE_FIELDS))
    return UpsertSummary(len(to_create), len(to_update), unchanged)


def ingest_csv(path: Path) -> UpsertSummary:
    rows = parse_match_csv(path)
    if not rows:
        logger.warning("no played matches in %s; nothing ingested", path.name)
    return ingest_rows(rows)


def ingest_directory(raw_dir: Path) -> tuple[int, UpsertSummary]:
    """Ingest every `D1_*.csv` in `raw_dir` in season order; returns (files, summary)."""
    paths = sorted(raw_dir.glob("D1_*.csv"))
    if not paths:
        logger.warning("no D1_*.csv files found in %s", raw_dir)
    total = UpsertSummary()
    for path in paths:
        total = total + ingest_csv(path)
    return len(paths), total
