from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from football.models import Fixture, Team

pytestmark = pytest.mark.django_db

RECORDED = Path(__file__).parent / "recorded" / "openligadb_sample.json"


@pytest.fixture
def openligadb(monkeypatch: pytest.MonkeyPatch) -> None:
    payload: list[dict[str, Any]] = json.loads(RECORDED.read_text())
    monkeypatch.setattr("bundespredict.data.fixtures.fetch_season_json", lambda start_year: payload)


def test_the_readme_setup_on_an_empty_database_serves_the_matchday(
    loaded_results: Path,
    openligadb: None,
    run_command: Callable[..., str],
    api_client: APIClient,
) -> None:
    # The test database is migrated while `teams` is empty, which is exactly a fresh local
    # setup: migration 0004 has no rows to give codes to, so ingest has to do it.
    run_command("refit", skip_download=True, as_of=date(2025, 6, 1))
    run_command("download_fixtures", season=2026)
    # The recorded fixtures kicked off in August 2026; move them ahead of "now" so they count
    # as the next matchday.
    Fixture.objects.update(kickoff_utc=timezone.now() + timedelta(days=2))

    response = api_client.get("/api/v1/fixtures")

    assert response.status_code == 200
    # Only Bayern v Stuttgart has both clubs in the synthetic result history, so it is the one
    # fixture the run can price.
    assert [(card["home"]["code"], card["away"]["code"]) for card in response.json()] == [
        ("FCB", "VFB")
    ]
    # Clubs that arrive through the fixture feed alone get their identity too.
    assert Team.objects.get(name="Hamburger SV").code == "HSV"
