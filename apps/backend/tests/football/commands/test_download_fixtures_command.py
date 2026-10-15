from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from django.core.management.base import CommandError

from football.models import Fixture, Team

pytestmark = pytest.mark.django_db

RECORDED = Path(__file__).parent / "recorded" / "openligadb_sample.json"


@pytest.fixture
def openligadb(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Serve the recorded OpenLigaDB payload instead of calling the API."""
    payload: list[dict[str, Any]] = json.loads(RECORDED.read_text())
    requested: list[int] = []

    def recorded_response(start_year: int) -> list[dict[str, Any]]:
        requested.append(start_year)
        return payload

    monkeypatch.setattr("bundespredict.data.fixtures.fetch_season_json", recorded_response)
    return payload


def test_stores_the_unplayed_matches_with_aware_kickoffs(
    openligadb: list[dict[str, Any]], run_command: Callable[..., str]
) -> None:
    summary = run_command("download_fixtures", season=2026)

    assert summary == (
        "download_fixtures: season 2627, 3 upcoming fixtures "
        "(3 created, 0 updated, 0 removed, 0 unchanged)"
    )
    bayern_match = Fixture.objects.get(home__name="Bayern Munich")
    assert bayern_match.kickoff_utc == datetime(2026, 8, 28, 18, 30, tzinfo=UTC)
    assert bayern_match.matchday == 1
    assert Team.objects.filter(name="Hamburger SV").exists()


def test_second_run_changes_no_rows(
    openligadb: list[dict[str, Any]],
    run_command: Callable[..., str],
    table_rows: Callable[[Any], list[tuple[object, ...]]],
) -> None:
    run_command("download_fixtures", season=2026)
    before = {model: table_rows(model) for model in (Fixture, Team)}

    summary = run_command("download_fixtures", season=2026)

    assert summary.endswith("(0 created, 0 updated, 0 removed, 3 unchanged)")
    assert {model: table_rows(model) for model in before} == before


def test_a_rescheduled_kickoff_updates_in_place_and_played_matches_drop_out(
    openligadb: list[dict[str, Any]], run_command: Callable[..., str]
) -> None:
    run_command("download_fixtures", season=2026)
    ids_before = dict(Fixture.objects.values_list("home__name", "id"))

    for entry in openligadb:
        if entry["team1"]["teamName"] == "FC Bayern München":
            entry["matchDateTimeUTC"] = "2026-08-28T19:30:00Z"
        if entry["team1"]["teamName"] == "Borussia Dortmund":
            entry["matchIsFinished"] = True
    summary = run_command("download_fixtures", season=2026)

    assert summary.endswith("(0 created, 1 updated, 1 removed, 1 unchanged)")
    assert Fixture.objects.get(home__name="Bayern Munich").kickoff_utc.hour == 19
    assert Fixture.objects.get(home__name="Bayern Munich").id == ids_before["Bayern Munich"]
    assert not Fixture.objects.filter(home__name="Borussia Dortmund").exists()


def test_an_empty_payload_leaves_the_schedule_alone(
    openligadb: list[dict[str, Any]], run_command: Callable[..., str]
) -> None:
    run_command("download_fixtures", season=2026)
    openligadb.clear()

    summary = run_command("download_fixtures", season=2026)

    assert summary.startswith("download_fixtures: season 2627, 0 upcoming fixtures")
    assert Fixture.objects.count() == 3


def test_default_season_follows_the_calendar(
    openligadb: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    run_command: Callable[..., str],
) -> None:
    requested: list[int] = []

    def recorded_response(year: int) -> list[dict[str, Any]]:
        requested.append(year)
        return openligadb

    monkeypatch.setattr("bundespredict.data.fixtures.fetch_season_json", recorded_response)
    monkeypatch.setattr(
        "football.management.commands.download_fixtures.today_utc",
        lambda: datetime(2026, 7, 1, tzinfo=UTC).date(),
    )

    run_command("download_fixtures")

    assert requested == [2026]


def test_network_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch, run_command: Callable[..., str]
) -> None:
    def unreachable(start_year: int) -> list[dict[str, Any]]:
        raise OSError("name resolution failed")

    monkeypatch.setattr("bundespredict.data.fixtures.fetch_season_json", unreachable)

    with pytest.raises(CommandError, match="name resolution failed"):
        run_command("download_fixtures", season=2026)
