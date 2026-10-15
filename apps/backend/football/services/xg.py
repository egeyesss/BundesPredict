"""Understat per-match xG -> `Match.home_xg` / `Match.away_xg`.

xG is joined onto the results history rather than owning rows: football-data decides which
matches exist, and Understat only fills the two xG columns. A row with no matching `Match` is
counted and skipped, never inserted. The stored values are final-match xG; they are only safe
because training reads rolling averages over matches strictly before kickoff.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction

from bundespredict.data.understat import UnderstatMatch
from football.models import Match, Team, TeamAlias

logger = logging.getLogger(__name__)

SOURCE = "understat"


@dataclass(frozen=True)
class XgSummary:
    seasons: int
    parsed: int
    matched: int
    unmatched: int
    updated: int


def _team_ids_by_name() -> dict[str, int]:
    by_name = dict(Team.objects.values_list("name", "id"))
    for alias, team_id in TeamAlias.objects.filter(source=SOURCE).values_list("alias", "team_id"):
        by_name.setdefault(alias, team_id)
    return by_name


def ingest_xg(seasons: dict[str, list[UnderstatMatch]]) -> XgSummary:
    """Backfill xG on the matching matches; only rows whose xG actually changed are written."""
    team_ids = _team_ids_by_name()
    with transaction.atomic():
        matches = {
            (m.season, m.home_id, m.away_id): m
            for m in Match.objects.filter(season__in=list(seasons))
        }
        parsed = matched = unmatched = 0
        to_update: list[Match] = []
        for rows in seasons.values():
            for row in rows:
                parsed += 1
                home_id = team_ids.get(row.home)
                away_id = team_ids.get(row.away)
                match = (
                    matches.get((row.season, home_id, away_id))
                    if home_id is not None and away_id is not None
                    else None
                )
                if match is None:
                    unmatched += 1
                    logger.warning(
                        "understat row without a fixture: %s %s vs %s",
                        row.season,
                        row.home,
                        row.away,
                    )
                    continue
                matched += 1
                if (match.home_xg, match.away_xg) != (row.home_xg, row.away_xg):
                    match.home_xg = row.home_xg
                    match.away_xg = row.away_xg
                    to_update.append(match)
        Match.objects.bulk_update(to_update, ["home_xg", "away_xg"])
    return XgSummary(
        seasons=len(seasons),
        parsed=parsed,
        matched=matched,
        unmatched=unmatched,
        updated=len(to_update),
    )
