"""Upcoming fixtures: mirror the OpenLigaDB schedule into `Fixture` rows.

The source is authoritative for the schedule (kickoffs get rescheduled, played matches drop
out of "upcoming"), so stored fixtures of the affected seasons are reconciled to it. The sync
works on the natural key rather than deleting and re-inserting, which keeps fixture ids stable
across runs and makes a second run over the same payload a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

from django.db import transaction

from bundespredict.data.fixtures import FixtureRow
from bundespredict.data.team_aliases import OPENLIGADB_ALIASES
from football.models import Fixture

from .teams import ensure_teams

SOURCE = "openligadb"


@dataclass(frozen=True)
class ScheduleSummary:
    created: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0

    @property
    def stored(self) -> int:
        return self.created + self.updated + self.unchanged


def sync_fixtures(rows: list[FixtureRow]) -> ScheduleSummary:
    """Reconcile the stored schedule of every season present in `rows` with `rows`.

    An empty payload leaves the table alone: it cannot say which season it was for, and an
    upstream hiccup must not wipe the schedule.
    """
    if not rows:
        return ScheduleSummary()
    with transaction.atomic():
        team_ids = ensure_teams(
            {r.home for r in rows} | {r.away for r in rows},
            source=SOURCE,
            aliases=OPENLIGADB_ALIASES,
        )
        desired = {
            (r.season, r.matchday, team_ids[r.home], team_ids[r.away]): r.kickoff_utc.replace(
                tzinfo=UTC
            )
            for r in rows
        }
        seasons = {r.season for r in rows}
        existing = {
            (f.season, f.matchday, f.home_id, f.away_id): f
            for f in Fixture.objects.filter(season__in=seasons)
        }

        # A frozen prediction keeps its fixture after the match is played, so it can be resolved.
        stale_ids = list(
            Fixture.objects.filter(
                id__in=[f.id for key, f in existing.items() if key not in desired],
                frozen_prediction__isnull=True,
            ).values_list("id", flat=True)
        )
        to_update: list[Fixture] = []
        to_create: list[Fixture] = []
        unchanged = 0
        for key, kickoff in desired.items():
            current = existing.get(key)
            if current is None:
                to_create.append(
                    Fixture(
                        season=key[0],
                        matchday=key[1],
                        home_id=key[2],
                        away_id=key[3],
                        kickoff_utc=kickoff,
                    )
                )
            elif current.kickoff_utc != kickoff:
                current.kickoff_utc = kickoff
                to_update.append(current)
            else:
                unchanged += 1

        Fixture.objects.filter(id__in=stale_ids).delete()
        Fixture.objects.bulk_update(to_update, ["kickoff_utc"])
        Fixture.objects.bulk_create(to_create)
    return ScheduleSummary(len(to_create), len(to_update), len(stale_ids), unchanged)
