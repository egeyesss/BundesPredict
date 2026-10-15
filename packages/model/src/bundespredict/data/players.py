"""Squad ingest (Transfermarkt cache -> DB) and the player lookup it serves.

The scrape writes raw HTML to ``data/tm_cache/``; this module turns parsed
rows into database state and answers "who is X?" for the agent. Ingest is the
only writer and follows the fixtures-table discipline: canonicalize every club
name up front (an unmapped club raises before any write), then mirror the
source — a team's roster is replaced wholesale, because players transfer away
and a stale row would ground an adjustment in a player who left.

``teams.tm_id`` is established here too: the league page pairs Transfermarkt's
numeric club id with a club name we can canonicalize, and once stored the id
is the join key for every future scrape. A conflicting id (same team, new
number) raises — that means our name mapping broke, not Transfermarkt.

Lookup mirrors the seeded-JSON matcher the agent started with: accent- and
case-insensitive, full name first, then last name. Importance is *derived*,
not hand-labelled: a player's standing by market value within his own squad
(top ~20% -> "high", next ~30% -> "medium", rest "low"). That rule lives here
so the tool description and the data can't drift apart.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Player, SquadValue, Team, TeamAlias
from .transfermarkt import LeagueClub, SquadPlayer, canonical_club_name

SOURCE = "transfermarkt"

# Market-value percentile cutoffs within a squad. Full kader pages list ~40
# contracted players including youth, so "key" is the top ~20% (≈ the first-XI
# core — a strict decile of 40 is 4 players and calls a €60m striker "medium"),
# the next band is a regular starter, the rest are squad depth.
HIGH_PERCENTILE = 0.8
MEDIUM_PERCENTILE = 0.5


def normalize_name(name: str) -> str:
    """Casefold and strip accents so "Sesko" matches "Šeško"."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().strip()


@dataclass(frozen=True)
class DbPlayer:
    """A squad member as the lookup returns it, team name canonical."""

    name: str
    team: str
    position: str
    market_value_eur: int | None
    importance: Literal["high", "medium", "low"]  # value standing within squad
    scraped_at: datetime


@dataclass(frozen=True)
class SquadIngestSummary:
    teams_linked: int  # teams whose tm_id was set or confirmed
    players_stored: int
    squad_values_stored: int


def _resolve_and_link_teams(session: Session, clubs: list[LeagueClub]) -> dict[int, int]:
    """Map tm club id -> teams.id, creating teams and storing tm_id.

    Every club canonicalizes before any write (fail loudly on an unmapped
    name). Clubs our results history never saw still get a teams row — same
    policy as the fixtures ingest — so a freshly promoted side is
    representable the moment Transfermarkt lists it.
    """
    tm_to_canonical = {club.tm_id: canonical_club_name(club.name) for club in clubs}
    tm_to_raw = {club.tm_id: club.name for club in clubs}
    canonicals = sorted(set(tm_to_canonical.values()))

    session.execute(
        pg_insert(Team)
        .values([{"name": name} for name in canonicals])
        .on_conflict_do_nothing(index_elements=["name"])
    )
    name_to_row = {
        name: (team_id, tm_id)
        for team_id, name, tm_id in session.execute(
            select(Team.id, Team.name, Team.tm_id).where(Team.name.in_(canonicals))
        )
    }

    for tm_id, canonical in tm_to_canonical.items():
        team_id, existing_tm_id = name_to_row[canonical]
        if existing_tm_id is None:
            session.execute(update(Team).where(Team.id == team_id).values(tm_id=tm_id))
        elif existing_tm_id != tm_id:
            raise ValueError(
                f"team {canonical!r} already linked to tm_id {existing_tm_id}, "
                f"but the league page says {tm_id} — alias map or source drifted"
            )

    session.execute(
        pg_insert(TeamAlias)
        .values(
            [
                {"alias": tm_to_raw[tm_id], "source": SOURCE, "team_id": name_to_row[canon][0]}
                for tm_id, canon in tm_to_canonical.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["alias"])
    )
    return {tm_id: name_to_row[canon][0] for tm_id, canon in tm_to_canonical.items()}


def ingest_squads(
    session: Session,
    clubs: list[LeagueClub],
    squads: dict[int, list[SquadPlayer]],
    *,
    scraped_at: datetime,
) -> SquadIngestSummary:
    """Store league-page squad values and (where scraped) full rosters.

    ``clubs`` may span several seasons (historical league pages feed the
    value-implied shrinkage prior); ``squads`` maps a tm club id to its
    *current* roster and replaces that team's players wholesale. Commits once
    at the end so a mid-ingest failure leaves the previous snapshot intact.
    """
    team_ids = _resolve_and_link_teams(session, clubs)

    n_values = 0
    for club in clubs:
        if club.squad_value_eur is None:
            continue
        stmt = pg_insert(SquadValue).values(
            season=club.season,
            team_id=team_ids[club.tm_id],
            value_eur=club.squad_value_eur,
            scraped_at=scraped_at,
        )
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_squad_value_season_team",
                set_={"value_eur": stmt.excluded.value_eur, "scraped_at": stmt.excluded.scraped_at},
            )
        )
        n_values += 1

    n_players = 0
    # A loaned player can be listed on two clubs' pages; tm_id is unique, so
    # the first club (stable: ascending tm club id) claims him and later
    # listings are skipped. The mirror is rebuilt every run, so this stays
    # deterministic rather than depending on scrape order.
    claimed: set[int] = set()
    for tm_club_id in sorted(squads):
        roster = squads[tm_club_id]
        if tm_club_id not in team_ids:
            raise ValueError(f"squad for unknown tm club id {tm_club_id} — not on a league page")
        team_id = team_ids[tm_club_id]
        session.execute(delete(Player).where(Player.team_id == team_id))
        for p in roster:
            if p.tm_id in claimed:
                continue
            claimed.add(p.tm_id)
            session.add(
                Player(
                    tm_id=p.tm_id,
                    team_id=team_id,
                    name=p.name,
                    position=p.position,
                    market_value_eur=p.market_value_eur,
                    scraped_at=scraped_at,
                )
            )
            n_players += 1

    session.commit()
    return SquadIngestSummary(
        teams_linked=len(team_ids), players_stored=n_players, squad_values_stored=n_values
    )


def _importance(value: int | None, squad_values: list[int]) -> Literal["high", "medium", "low"]:
    """Value standing within the squad: top ~20% high, next ~30% medium."""
    if value is None or not squad_values:
        return "low"
    below = sum(1 for v in squad_values if v < value)
    percentile = below / len(squad_values)
    if percentile >= HIGH_PERCENTILE:
        return "high"
    if percentile >= MEDIUM_PERCENTILE:
        return "medium"
    return "low"


def find_player(session: Session, query: str) -> DbPlayer | None:
    """Find a squad member by full or last name, accent/case-insensitive.

    Full-name matches always win; last-name matches are a fallback and, on a
    collision (two squads with a "Müller"), the more valuable player wins —
    the likelier subject of a "X is out" claim. Returns ``None`` when the
    players table is empty (caller falls back to the seeded offline data).
    """
    rows: list[tuple[str, str, str, int | None, datetime]] = [
        (r[0], r[1], r[2], r[3], r[4])
        for r in session.execute(
            select(
                Player.name,
                Team.name,
                Player.position,
                Player.market_value_eur,
                Player.scraped_at,
            )
            .join(Team, Team.id == Player.team_id)
            .order_by(Player.market_value_eur.desc().nulls_last())
        )
    ]
    if not rows:
        return None

    values_by_team: dict[str, list[int]] = {}
    for _, team, _, value, _ in rows:
        if value is not None:
            values_by_team.setdefault(team, []).append(value)

    def to_player(row: tuple[str, str, str, int | None, datetime]) -> DbPlayer:
        name, team, position, value, scraped_at = row
        return DbPlayer(
            name=name,
            team=team,
            position=position,
            market_value_eur=value,
            importance=_importance(value, values_by_team.get(team, [])),
            scraped_at=scraped_at,
        )

    key = normalize_name(query)
    last_key = normalize_name(query.split()[-1]) if query.split() else key
    last_match: DbPlayer | None = None
    for row in rows:  # value-descending, so the first last-name hit is the richest
        if normalize_name(row[0]) == key:
            return to_player(row)
        if last_match is None and normalize_name(row[0].split()[-1]) == last_key:
            last_match = to_player(row)
    return last_match


def squad_values_by_season(session: Session) -> dict[str, dict[str, int]]:
    """All stored squad values as ``{season: {canonical team: value_eur}}``.

    The backtest feeds these into the value-implied shrinkage targets; serving
    only ever needs the current season's slice.
    """
    out: dict[str, dict[str, int]] = {}
    for season, team, value in session.execute(
        select(SquadValue.season, Team.name, SquadValue.value_eur).join(
            Team, Team.id == SquadValue.team_id
        )
    ):
        out.setdefault(season, {})[team] = value
    return out
