"""Upcoming-fixture schedule: OpenLigaDB fetch, parse, ingest, and lookup.

Results history comes from football-data CSVs, but those only exist after a
match is played — "who does Dortmund play next?" needs the schedule. OpenLigaDB
(https://api.openligadb.de) publishes the Bundesliga calendar, including future
matchdays, keyless.

The pieces are deliberately separable: :func:`parse_fixtures` is pure (JSON in,
typed rows out — testable from a recorded payload), :func:`fetch_season_json`
is the only network call, and :func:`ingest_fixtures` is the only DB writer.
Ingest replaces the season's rows wholesale inside one transaction: the source
is authoritative for the schedule (kickoffs get rescheduled, played matches drop
out of "upcoming"), so mirroring beats reconciling.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from .models import Fixture, Team, TeamAlias
from .team_aliases import OPENLIGADB_ALIASES, canonical_team_name

SOURCE = "openligadb"
_API_URL = "https://api.openligadb.de/getmatchdata/bl1/{year}"


@dataclass(frozen=True)
class FixtureRow:
    """One scheduled match parsed from the source, teams still source-spelled."""

    season: str  # e.g. "2627"
    matchday: int
    kickoff_utc: datetime  # naive UTC
    home: str
    away: str


@dataclass(frozen=True)
class UpcomingFixture:
    """One scheduled match as the agent reports it, teams canonical."""

    kickoff_utc: datetime
    matchday: int
    season: str
    home: str
    away: str


def season_code(start_year: int) -> str:
    """2026 -> "2627", matching the season codes used for matches."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def fetch_season_json(start_year: int) -> list[dict[str, Any]]:
    """Download one season's full match list (played and scheduled)."""
    with urllib.request.urlopen(_API_URL.format(year=start_year), timeout=30) as resp:
        return list(json.loads(resp.read().decode("utf-8")))


def parse_fixtures(payload: list[dict[str, Any]], start_year: int) -> list[FixtureRow]:
    """Extract the *unplayed* matches from an OpenLigaDB season payload.

    Played matches are dropped — results are football-data's job — and so is
    anything without a matchday or kickoff (defensive; the API has been known to
    carry placeholder entries early in a season).
    """
    rows: list[FixtureRow] = []
    for entry in payload:
        if entry.get("matchIsFinished"):
            continue
        group = entry.get("group") or {}
        matchday = group.get("groupOrderID")
        kickoff_raw = entry.get("matchDateTimeUTC")
        team1 = (entry.get("team1") or {}).get("teamName")
        team2 = (entry.get("team2") or {}).get("teamName")
        if not (matchday and kickoff_raw and team1 and team2):
            continue
        kickoff = datetime.fromisoformat(kickoff_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        rows.append(
            FixtureRow(
                season=season_code(start_year),
                matchday=int(matchday),
                kickoff_utc=kickoff,
                home=str(team1),
                away=str(team2),
            )
        )
    return rows


def _resolve_team_ids(session: Session, raw_names: set[str]) -> dict[str, int]:
    """Canonicalize source names, creating teams/aliases for fresh promotions.

    Mirrors the match ingest's discipline: every name canonicalizes up front (an
    unmapped club raises before any write), and a club our result history has
    never seen — a team promoted from below the data's horizon — gets a teams
    row now so its fixtures are representable. It simply has no ratings until it
    plays top-flight matches.
    """
    raw_to_canonical = {
        raw: canonical_team_name(raw, source_aliases=OPENLIGADB_ALIASES) for raw in raw_names
    }
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


def ingest_fixtures(session: Session, rows: list[FixtureRow]) -> int:
    """Replace the stored schedule for every season present in ``rows``.

    Delete-then-insert in one transaction keeps the table an exact mirror of the
    source: rescheduled kickoffs update, played matches disappear. Returns the
    number of fixtures stored.
    """
    if not rows:
        return 0
    team_ids = _resolve_team_ids(session, {r.home for r in rows} | {r.away for r in rows})
    seasons = {r.season for r in rows}
    session.execute(delete(Fixture).where(Fixture.season.in_(seasons)))
    session.add_all(
        Fixture(
            season=r.season,
            matchday=r.matchday,
            kickoff_utc=r.kickoff_utc,
            home_id=team_ids[r.home],
            away_id=team_ids[r.away],
        )
        for r in rows
    )
    session.commit()
    return len(rows)


def upcoming_fixtures(
    session: Session,
    *,
    team: str | None = None,
    on_or_after: date,
    n: int = 9,
) -> tuple[UpcomingFixture, ...]:
    """The next ``n`` scheduled fixtures from ``on_or_after``, soonest first.

    ``team`` (canonical name) narrows to one club's schedule. Raises
    ``ValueError`` for an unknown team so an agent typo fails loudly instead of
    returning an empty schedule that reads like "no fixtures".
    """
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(
            Fixture.kickoff_utc,
            Fixture.matchday,
            Fixture.season,
            home_team.name,
            away_team.name,
        )
        .join(home_team, home_team.id == Fixture.home_id)
        .join(away_team, away_team.id == Fixture.away_id)
        .where(Fixture.kickoff_utc >= datetime.combine(on_or_after, datetime.min.time()))
        .order_by(Fixture.kickoff_utc, Fixture.id)
        .limit(n)
    )
    if team is not None:
        team_id = session.execute(select(Team.id).where(Team.name == team)).scalar_one_or_none()
        if team_id is None:
            raise ValueError(f"unknown team: {team!r}")
        stmt = stmt.where((Fixture.home_id == team_id) | (Fixture.away_id == team_id))

    return tuple(
        UpcomingFixture(kickoff_utc=r[0], matchday=r[1], season=r[2], home=r[3], away=r[4])
        for r in session.execute(stmt).all()
    )
