"""Transfermarkt snapshot -> `Team.tm_id`, `SquadValue` and `Player` rows.

The cache is parsed into dataclasses by the library; this module only writes. Every club name
is canonicalized before any write, so an unmapped club raises and the previous snapshot keeps
serving. A team's roster mirrors the source (players who left are removed), reconciled by
`tm_id` so re-ingesting the same snapshot changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from bundespredict.data.tm_scrape import TransfermarktSnapshot
from bundespredict.data.transfermarkt import LeagueClub, SquadPlayer, canonical_club_name
from football.models import Player, SquadValue, Team, TeamAlias

SOURCE = "transfermarkt"


@dataclass(frozen=True)
class SquadSummary:
    teams_linked: int
    players_stored: int
    players_removed: int
    squad_values_stored: int
    changed: int


def _link_teams(clubs: list[LeagueClub]) -> tuple[dict[int, int], int]:
    """Map tm club id -> team id, creating teams and storing `tm_id`; also count rows written."""
    tm_to_canonical = {club.tm_id: canonical_club_name(club.name) for club in clubs}
    tm_to_raw = {club.tm_id: club.name for club in clubs}
    canonical_names = sorted(set(tm_to_canonical.values()))

    written = 0
    teams = {t.name: t for t in Team.objects.filter(name__in=canonical_names)}
    missing = [name for name in canonical_names if name not in teams]
    if missing:
        Team.objects.bulk_create([Team(name=name) for name in missing], ignore_conflicts=True)
        written += len(missing)
        teams = {t.name: t for t in Team.objects.filter(name__in=canonical_names)}

    for tm_id, canonical in tm_to_canonical.items():
        team = teams[canonical]
        if team.tm_id is None:
            team.tm_id = tm_id
            team.save(update_fields=["tm_id"])
            written += 1
        elif team.tm_id != tm_id:
            raise ValueError(
                f"team {canonical!r} already linked to tm_id {team.tm_id}, "
                f"but the league page says {tm_id}: alias map or source drifted"
            )

    known = set(
        TeamAlias.objects.filter(alias__in=tm_to_raw.values()).values_list("alias", flat=True)
    )
    new_aliases = [
        TeamAlias(alias=tm_to_raw[tm_id], source=SOURCE, team_id=teams[canonical].id)
        for tm_id, canonical in tm_to_canonical.items()
        if tm_to_raw[tm_id] not in known
    ]
    TeamAlias.objects.bulk_create(new_aliases, ignore_conflicts=True)
    written += len(new_aliases)
    return {tm_id: teams[canonical].id for tm_id, canonical in tm_to_canonical.items()}, written


def _sync_squad_values(
    clubs: list[LeagueClub], team_ids: dict[int, int], scraped_at: datetime
) -> tuple[int, int]:
    """Upsert squad values; returns (values stored, rows written)."""
    wanted = {
        (club.season, team_ids[club.tm_id]): club.squad_value_eur
        for club in clubs
        if club.squad_value_eur is not None
    }
    existing = {(v.season, v.team_id): v for v in SquadValue.objects.all()}
    to_create: list[SquadValue] = []
    to_update: list[SquadValue] = []
    for (season, team_id), value in wanted.items():
        current = existing.get((season, team_id))
        if current is None:
            to_create.append(
                SquadValue(season=season, team_id=team_id, value_eur=value, scraped_at=scraped_at)
            )
        elif current.value_eur != value or current.scraped_at != scraped_at:
            current.value_eur = value
            current.scraped_at = scraped_at
            to_update.append(current)
    SquadValue.objects.bulk_create(to_create)
    SquadValue.objects.bulk_update(to_update, ["value_eur", "scraped_at"])
    return len(wanted), len(to_create) + len(to_update)


def _sync_players(
    squads: dict[int, list[SquadPlayer]], team_ids: dict[int, int], scraped_at: datetime
) -> tuple[int, int, int]:
    """Mirror the scraped rosters; returns (players stored, players removed, rows written)."""
    for tm_club_id in squads:
        if tm_club_id not in team_ids:
            raise ValueError(f"squad for unknown tm club id {tm_club_id}: not on a league page")

    # A loaned player can be listed on two clubs' pages and `tm_id` is unique, so the lowest
    # club id claims him. Walking clubs in ascending order keeps that deterministic.
    wanted: dict[int, tuple[int, SquadPlayer]] = {}
    for tm_club_id in sorted(squads):
        for player in squads[tm_club_id]:
            wanted.setdefault(player.tm_id, (team_ids[tm_club_id], player))

    scraped_team_ids = {team_ids[tm_club_id] for tm_club_id in squads}
    existing = {
        p.tm_id: p
        for p in Player.objects.filter(team_id__in=scraped_team_ids)
        | Player.objects.filter(tm_id__in=wanted)
    }

    stale = [p.id for tm_id, p in existing.items() if tm_id not in wanted]
    to_create: list[Player] = []
    to_update: list[Player] = []
    for tm_id, (team_id, scraped) in wanted.items():
        current = existing.get(tm_id)
        if current is None:
            to_create.append(
                Player(
                    tm_id=tm_id,
                    team_id=team_id,
                    name=scraped.name,
                    position=scraped.position,
                    market_value_eur=scraped.market_value_eur,
                    scraped_at=scraped_at,
                )
            )
        elif (
            current.team_id,
            current.name,
            current.position,
            current.market_value_eur,
            current.scraped_at,
        ) != (team_id, scraped.name, scraped.position, scraped.market_value_eur, scraped_at):
            current.team_id = team_id
            current.name = scraped.name
            current.position = scraped.position
            current.market_value_eur = scraped.market_value_eur
            current.scraped_at = scraped_at
            to_update.append(current)

    Player.objects.filter(id__in=stale).delete()
    Player.objects.bulk_update(
        to_update, ["team", "name", "position", "market_value_eur", "scraped_at"]
    )
    Player.objects.bulk_create(to_create)
    return len(wanted), len(stale), len(to_create) + len(to_update) + len(stale)


def ingest_snapshot(snapshot: TransfermarktSnapshot) -> SquadSummary:
    """Store league-page squad values and the scraped rosters in one transaction."""
    with transaction.atomic():
        team_ids, link_writes = _link_teams(snapshot.clubs)
        values_stored, value_writes = _sync_squad_values(
            snapshot.clubs, team_ids, snapshot.scraped_at
        )
        players_stored, players_removed, player_writes = _sync_players(
            snapshot.squads, team_ids, snapshot.scraped_at
        )
    return SquadSummary(
        teams_linked=len(team_ids),
        players_stored=players_stored,
        players_removed=players_removed,
        squad_values_stored=values_stored,
        changed=link_writes + value_writes + player_writes,
    )
