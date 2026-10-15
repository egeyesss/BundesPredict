"""Team and alias rows shared by every ingest.

Each source spells clubs its own way. Names are canonicalized before anything is written, so an
unmapped club raises `UnmappedTeamError` and leaves the database untouched.
"""

from __future__ import annotations

from collections.abc import Iterable

from bundespredict.data.team_aliases import canonical_team_name
from football.models import Team, TeamAlias


def ensure_teams(
    raw_names: Iterable[str], *, source: str, aliases: dict[str, str] | None = None
) -> dict[str, int]:
    """Make sure a team row and a source alias exist for every raw name; map name -> team id.

    `aliases` is the source's name map (football-data's when omitted). Only missing rows are
    inserted, so re-running consumes no id sequence values and changes nothing.
    """
    unique_raw = sorted(set(raw_names))
    if aliases is None:
        raw_to_canonical = {raw: canonical_team_name(raw) for raw in unique_raw}
    else:
        raw_to_canonical = {
            raw: canonical_team_name(raw, source_aliases=aliases) for raw in unique_raw
        }
    canonical_names = sorted(set(raw_to_canonical.values()))
    if not canonical_names:
        return {}

    known = dict(Team.objects.filter(name__in=canonical_names).values_list("name", "id"))
    missing = [name for name in canonical_names if name not in known]
    if missing:
        Team.objects.bulk_create([Team(name=name) for name in missing], ignore_conflicts=True)
        known = dict(Team.objects.filter(name__in=canonical_names).values_list("name", "id"))

    known_aliases = set(
        TeamAlias.objects.filter(alias__in=raw_to_canonical).values_list("alias", flat=True)
    )
    new_aliases = [
        TeamAlias(alias=raw, source=source, team_id=known[canonical])
        for raw, canonical in raw_to_canonical.items()
        if raw not in known_aliases
    ]
    if new_aliases:
        TeamAlias.objects.bulk_create(new_aliases, ignore_conflicts=True)
    return {raw: known[canonical] for raw, canonical in raw_to_canonical.items()}
