"""Ingest parsed season CSVs into Postgres.

Idempotent by construction: teams/aliases upsert with ``ON CONFLICT DO NOTHING``
and matches upsert on their natural key ``(season, home_id, away_id)`` with
``ON CONFLICT DO UPDATE``, so re-running never duplicates and refreshes any
corrected upstream values. Team names are canonicalized up front, so an unmapped
club raises before any write touches the database.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .db import make_engine, make_session_factory
from .models import Match, Team, TeamAlias
from .parse import MatchRow, parse_match_csv, season_from_path
from .team_aliases import canonical_team_name

SOURCE = "football-data"
logger = logging.getLogger(__name__)

# Match columns that should never be overwritten on conflict (identity + natural key).
_MATCH_IMMUTABLE = frozenset({"id", "season", "home_id", "away_id"})


@dataclass(frozen=True, slots=True)
class IngestStats:
    season: str
    matches_upserted: int
    teams_seen: int


def _resolve_team_ids(session: Session, raw_names: Iterable[str]) -> dict[str, int]:
    """Canonicalize raw names, upsert teams + aliases, return raw-name -> team id.

    Canonicalization runs first for every name, so an unmapped club raises
    ``UnmappedTeamError`` before any row is written.
    """
    raw_to_canonical = {raw: canonical_team_name(raw) for raw in raw_names}
    canonicals = sorted(set(raw_to_canonical.values()))
    if not canonicals:
        return {}

    session.execute(
        pg_insert(Team)
        .values([{"name": name} for name in canonicals])
        .on_conflict_do_nothing(index_elements=["name"])
    )
    name_to_id = {
        name: team_id
        for team_id, name in session.execute(
            select(Team.id, Team.name).where(Team.name.in_(canonicals))
        )
    }

    session.execute(
        pg_insert(TeamAlias)
        .values(
            [
                {"alias": raw, "source": SOURCE, "team_id": name_to_id[canonical]}
                for raw, canonical in raw_to_canonical.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["alias"])
    )
    return {raw: name_to_id[canonical] for raw, canonical in raw_to_canonical.items()}


def _match_values(row: MatchRow, team_ids: dict[str, int]) -> dict[str, object]:
    values: dict[str, object] = {
        "season": row.season,
        "date": row.date,
        "home_id": team_ids[row.home_team],
        "away_id": team_ids[row.away_team],
    }
    # Copy every stat/odds field straight off the row (names line up with columns).
    for field in MatchRow.__dataclass_fields__:
        if field not in {"season", "date", "home_team", "away_team"}:
            values[field] = getattr(row, field)
    return values


def ingest_csv(session: Session, path: Path) -> IngestStats:
    """Parse and upsert one season CSV. Commits on success."""
    rows = parse_match_csv(path)
    if not rows:
        logger.warning("no played matches in %s; nothing ingested", path.name)
        return IngestStats(season_from_path(path), 0, 0)

    raw_names = {r.home_team for r in rows} | {r.away_team for r in rows}
    team_ids = _resolve_team_ids(session, raw_names)

    stmt = pg_insert(Match).values([_match_values(r, team_ids) for r in rows])
    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in Match.__table__.columns
        if col.name not in _MATCH_IMMUTABLE
    }
    stmt = stmt.on_conflict_do_update(constraint="uq_match_season_home_away", set_=update_cols)
    session.execute(stmt)
    session.commit()

    stats = IngestStats(rows[0].season, len(rows), len(set(team_ids.values())))
    logger.info(
        "ingested season %s: %d matches, %d teams",
        stats.season,
        stats.matches_upserted,
        stats.teams_seen,
    )
    return stats


def ingest_dir(session: Session, raw_dir: Path) -> list[IngestStats]:
    """Ingest every ``D1_*.csv`` in ``raw_dir`` in season order."""
    paths = sorted(raw_dir.glob("D1_*.csv"))
    if not paths:
        logger.warning("no D1_*.csv files found in %s", raw_dir)
    return [ingest_csv(session, path) for path in paths]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raw_dir = Path(__file__).resolve().parents[3] / "data" / "raw"
    engine = make_engine()
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        results = ingest_dir(session, raw_dir)
    total = sum(s.matches_upserted for s in results)
    print(f"Ingested {len(results)} season(s), {total} matches total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
