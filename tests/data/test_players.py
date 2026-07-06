"""Squad ingest + player lookup tests (real Postgres via the session fixture)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.data.models import Player, Team
from bundespredict.data.players import (
    find_player,
    ingest_squads,
    squad_values_by_season,
)
from bundespredict.data.team_aliases import UnmappedTeamError
from bundespredict.data.transfermarkt import LeagueClub, SquadPlayer

SCRAPED = datetime(2026, 7, 5, 8, 0)


def _club(
    tm_id: int, name: str, season: str = "2526", value: int | None = 100_000_000
) -> LeagueClub:
    return LeagueClub(
        tm_id=tm_id,
        slug=name.lower().replace(" ", "-"),
        name=name,
        season=season,
        squad_value_eur=value,
    )


def _squad_of(n: int, base_id: int, values: list[int | None]) -> list[SquadPlayer]:
    positions = ["Goalkeeper", "Centre-Back", "Central Midfield", "Centre-Forward"]
    return [
        SquadPlayer(
            tm_id=base_id + i,
            name=f"Player {base_id + i}",
            position=positions[i % 4],
            market_value_eur=values[i],
        )
        for i in range(n)
    ]


def test_ingest_links_tm_ids_and_stores_squads(session: Session) -> None:
    clubs = [_club(27, "Bayern Munich"), _club(16, "Borussia Dortmund", value=None)]
    squads = {27: _squad_of(20, 1000, [i * 1_000_000 for i in range(1, 21)])}
    summary = ingest_squads(session, clubs, squads, scraped_at=SCRAPED)

    assert summary.teams_linked == 2
    assert summary.players_stored == 20
    assert summary.squad_values_stored == 1  # Dortmund had no value on the page

    bayern = session.execute(select(Team).where(Team.name == "Bayern Munich")).scalar_one()
    assert bayern.tm_id == 27
    assert squad_values_by_season(session) == {"2526": {"Bayern Munich": 100_000_000}}


def test_reingest_replaces_roster(session: Session) -> None:
    clubs = [_club(27, "Bayern Munich")]
    ingest_squads(session, clubs, {27: _squad_of(20, 1000, [1_000_000] * 20)}, scraped_at=SCRAPED)
    # The transfer window happened: three players left, one arrived.
    ingest_squads(session, clubs, {27: _squad_of(18, 2000, [2_000_000] * 18)}, scraped_at=SCRAPED)

    names = set(session.execute(select(Player.name)).scalars())
    assert len(names) == 18
    assert all(name.startswith("Player 2") for name in names)


def test_unmapped_club_aborts_before_any_write(session: Session) -> None:
    clubs = [_club(27, "Bayern Munich"), _club(999, "TSV 1860 Munich")]
    with pytest.raises(UnmappedTeamError):
        ingest_squads(session, clubs, {}, scraped_at=SCRAPED)
    session.rollback()
    assert session.execute(select(Team.id)).all() == []


def test_conflicting_tm_id_raises(session: Session) -> None:
    ingest_squads(session, [_club(27, "Bayern Munich")], {}, scraped_at=SCRAPED)
    with pytest.raises(ValueError, match="already linked"):
        ingest_squads(session, [_club(28, "Bayern Munich")], {}, scraped_at=SCRAPED)
    session.rollback()


def test_find_player_accent_insensitive_with_importance(session: Session) -> None:
    values: list[int | None] = [
        50_000_000,
        *([20_000_000] * 8),
        *([5_000_000] * 6),
        *([500_000] * 5),
    ]
    squad = _squad_of(20, 1000, values)
    # Give the star an accented name; queries come in unaccented.
    squad[0] = SquadPlayer(
        tm_id=1000, name="Benjamín Šeško", position="Centre-Forward", market_value_eur=50_000_000
    )
    ingest_squads(session, [_club(23826, "RB Leipzig")], {23826: squad}, scraped_at=SCRAPED)

    found = find_player(session, "benjamin sesko")
    assert found is not None
    assert found.team == "RB Leipzig"
    assert found.importance == "high"  # top of the squad by value
    assert found.scraped_at == SCRAPED

    by_last_name = find_player(session, "Sesko")
    assert by_last_name is not None and by_last_name.name == "Benjamín Šeško"

    depth = find_player(session, "Player 1019")  # a €500k squad player
    assert depth is not None and depth.importance == "low"

    assert find_player(session, "Erling Haaland") is None  # wrong league


def test_last_name_collision_prefers_higher_value(session: Session) -> None:
    squad_a = [
        SquadPlayer(
            tm_id=1, name="Thomas Müller", position="Second Striker", market_value_eur=9_000_000
        )
    ]
    squad_b = [
        SquadPlayer(tm_id=2, name="Kevin Müller", position="Goalkeeper", market_value_eur=300_000)
    ]
    ingest_squads(
        session,
        [_club(27, "Bayern Munich"), _club(2036, "1.FC Heidenheim 1846")],
        {27: squad_a, 2036: squad_b},
        scraped_at=SCRAPED,
    )
    found = find_player(session, "Müller")
    assert found is not None and found.name == "Thomas Müller"


def test_find_player_on_empty_table_returns_none(session: Session) -> None:
    assert find_player(session, "anyone") is None


def test_player_listed_by_two_clubs_is_stored_once(session: Session) -> None:
    # Loan listings: the same tm player id can appear on both clubs' pages.
    loanee = SquadPlayer(
        tm_id=555, name="Loan Keeper", position="Goalkeeper", market_value_eur=800_000
    )
    ingest_squads(
        session,
        [_club(27, "Bayern Munich"), _club(2036, "1.FC Heidenheim 1846")],
        {27: [loanee], 2036: [loanee]},
        scraped_at=SCRAPED,
    )
    rows = session.execute(select(Player).where(Player.tm_id == 555)).scalars().all()
    assert len(rows) == 1
    # Ascending tm club id claims first: Bayern (27) before Heidenheim (2036).
    team = session.execute(select(Team).where(Team.id == rows[0].team_id)).scalar_one()
    assert team.name == "Bayern Munich"
