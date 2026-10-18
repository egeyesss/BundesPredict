from __future__ import annotations

from datetime import datetime

import pytest

from bundespredict.data.fixtures import FixtureRow
from bundespredict.data.team_aliases import UnmappedTeamError
from football.models import Fixture, Team
from football.services.schedule import sync_fixtures

pytestmark = pytest.mark.django_db


def row(home: str, away: str = "Borussia Dortmund") -> FixtureRow:
    return FixtureRow(
        season="2627",
        matchday=1,
        kickoff_utc=datetime(2026, 8, 29, 13, 30),
        home=home,
        away=away,
    )


def test_an_unmapped_club_aborts_before_any_write() -> None:
    with pytest.raises(UnmappedTeamError):
        sync_fixtures([row("Nonexistent FC")])

    assert not Fixture.objects.exists()
    assert not Team.objects.exists()


def test_a_club_without_result_history_gets_a_team_row() -> None:
    sync_fixtures([row("Hamburger SV")])

    assert Team.objects.filter(name="Hamburger SV").exists()
    assert Fixture.objects.get().home.name == "Hamburger SV"
