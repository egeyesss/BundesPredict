from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bundespredict.data.team_aliases import UnmappedTeamError
from bundespredict.data.tm_scrape import TransfermarktSnapshot
from bundespredict.data.transfermarkt import LeagueClub, SquadPlayer
from football.models import Player, Team
from football.services.squads import ingest_snapshot

pytestmark = pytest.mark.django_db

SCRAPED = datetime(2026, 7, 5, 8, 0, tzinfo=UTC)
BAYERN, HEIDENHEIM = 27, 2036

TRANSFER = SquadPlayer(
    tm_id=777, name="Moving Striker", position="Centre-Forward", market_value_eur=9_000_000
)


def club(tm_id: int, name: str) -> LeagueClub:
    return LeagueClub(
        tm_id=tm_id, slug=name.lower(), name=name, season="2526", squad_value_eur=100_000_000
    )


def ingest(clubs: list[LeagueClub], squads: dict[int, list[SquadPlayer]]) -> None:
    ingest_snapshot(TransfermarktSnapshot(clubs=clubs, squads=squads, scraped_at=SCRAPED))


def team_of(tm_id: int) -> str:
    return Player.objects.select_related("team").get(tm_id=tm_id).team.name


def test_an_unmapped_club_aborts_before_any_write() -> None:
    clubs = [club(BAYERN, "Bayern Munich"), club(999, "TSV 1860 Munich")]

    with pytest.raises(UnmappedTeamError):
        ingest(clubs, {})

    assert Team.objects.count() == 0


def test_a_club_that_changes_tm_id_is_rejected() -> None:
    ingest([club(BAYERN, "Bayern Munich")], {})

    with pytest.raises(ValueError, match="already linked"):
        ingest([club(28, "Bayern Munich")], {})


def test_a_player_listed_by_two_clubs_is_stored_once_under_the_lower_club_id() -> None:
    loanee = SquadPlayer(
        tm_id=555, name="Loan Keeper", position="Goalkeeper", market_value_eur=800_000
    )

    ingest(
        [club(BAYERN, "Bayern Munich"), club(HEIDENHEIM, "1.FC Heidenheim 1846")],
        {BAYERN: [loanee], HEIDENHEIM: [loanee]},
    )

    assert Player.objects.filter(tm_id=555).count() == 1
    assert team_of(555) == "Bayern Munich"


def test_a_transfer_to_a_club_that_is_rebuilt_first_moves_the_player() -> None:
    clubs = [club(BAYERN, "Bayern Munich"), club(HEIDENHEIM, "1.FC Heidenheim 1846")]
    ingest(clubs, {BAYERN: [], HEIDENHEIM: [TRANSFER]})

    ingest(clubs, {BAYERN: [TRANSFER], HEIDENHEIM: []})

    assert team_of(777) == "Bayern Munich"
    assert Player.objects.filter(tm_id=777).count() == 1


def test_a_transfer_from_a_club_that_is_no_longer_scraped_moves_the_player() -> None:
    ingest([club(HEIDENHEIM, "1.FC Heidenheim 1846")], {HEIDENHEIM: [TRANSFER]})

    # Heidenheim was relegated, so its squad page is not part of the next scrape.
    ingest([club(BAYERN, "Bayern Munich")], {BAYERN: [TRANSFER]})

    assert team_of(777) == "Bayern Munich"
    assert Player.objects.filter(tm_id=777).count() == 1


def test_a_squad_for_a_club_missing_from_the_league_page_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown tm club id"):
        ingest([club(BAYERN, "Bayern Munich")], {HEIDENHEIM: [TRANSFER]})

    assert Player.objects.count() == 0
