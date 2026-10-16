from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from bundespredict.data import tm_scrape
from football.models import Player, SquadValue, Team

pytestmark = pytest.mark.django_db

RECORDED = Path(__file__).parent / "recorded"
BAYERN_TM_ID = 27
HEIDENHEIM_TM_ID = 2036
SQUAD_FETCHED_AT = "2025-10-01T03:05:00+00:00"


def recorded_page(name: str) -> str:
    return gzip.open(RECORDED / name, "rt", encoding="utf-8").read()


@pytest.fixture(autouse=True)
def single_season_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin "today" to October 2025 and shrink the history to that season's league page."""
    monkeypatch.setattr(tm_scrape, "FIRST_SEASON", 2025)
    monkeypatch.setattr(
        "football.management.commands.scrape_transfermarkt.today_utc", lambda: date(2025, 10, 1)
    )


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """A cache as a previous scrape would have left it: the league page and two squads."""
    directory = tmp_path / "tm_cache"
    directory.mkdir()
    (directory / "league_2025.html").write_text(
        recorded_page("tm_league_2025.html.gz"), encoding="utf-8"
    )
    (directory / f"squad_{BAYERN_TM_ID}.html").write_text(
        recorded_page("tm_squad_bayern.html.gz"), encoding="utf-8"
    )
    (directory / f"squad_{HEIDENHEIM_TM_ID}.html").write_text(
        recorded_page("tm_squad_heidenheim.html.gz"), encoding="utf-8"
    )
    (directory / "meta.json").write_text(
        json.dumps(
            {
                f"squad_{BAYERN_TM_ID}.html": SQUAD_FETCHED_AT,
                f"squad_{HEIDENHEIM_TM_ID}.html": SQUAD_FETCHED_AT,
            }
        )
    )
    return directory


def test_ingest_from_cache_stores_values_players_and_links(
    cache_dir: Path, run_command: Callable[..., str]
) -> None:
    summary = run_command("scrape_transfermarkt", skip_fetch=True, cache_dir=str(cache_dir))

    assert summary.startswith("scrape_transfermarkt: 18 teams linked, 73 players (0 removed)")
    assert SquadValue.objects.filter(season="2526").count() == 18
    assert Team.objects.get(name="Bayern Munich").tm_id == BAYERN_TM_ID
    assert Player.objects.filter(team__name="Bayern Munich").count() == 40
    assert Player.objects.get(tm_id=607720).scraped_at == datetime(2025, 10, 1, 3, 5, tzinfo=UTC)


def test_second_run_changes_no_rows(
    cache_dir: Path,
    run_command: Callable[..., str],
    table_rows: Callable[[Any], list[tuple[object, ...]]],
) -> None:
    run_command("scrape_transfermarkt", skip_fetch=True, cache_dir=str(cache_dir))
    models = (Team, Player, SquadValue)
    before = {model: table_rows(model) for model in models}

    summary = run_command("scrape_transfermarkt", skip_fetch=True, cache_dir=str(cache_dir))

    assert summary.endswith("0 rows changed")
    assert {model: table_rows(model) for model in models} == before


def test_a_player_who_left_is_removed_and_a_new_value_is_stored(
    cache_dir: Path, run_command: Callable[..., str]
) -> None:
    run_command("scrape_transfermarkt", skip_fetch=True, cache_dir=str(cache_dir))
    squad_path = cache_dir / f"squad_{BAYERN_TM_ID}.html"
    squad_path.write_text(
        squad_path.read_text(encoding="utf-8").replace("€18.00m", "€19.00m"), encoding="utf-8"
    )
    urbig = Player.objects.get(tm_id=607720)
    assert urbig.market_value_eur == 18_000_000

    run_command("scrape_transfermarkt", skip_fetch=True, cache_dir=str(cache_dir))
    urbig.refresh_from_db()
    assert urbig.market_value_eur == 19_000_000

    # A fresh Bayern page without Urbig (he moved on) drops him from the roster.
    squad_path.write_text(
        squad_path.read_text(encoding="utf-8").replace(
            "/profil/spieler/607720", "/profil/spieler/1"
        ),
        encoding="utf-8",
    )
    summary = run_command("scrape_transfermarkt", skip_fetch=True, cache_dir=str(cache_dir))
    assert "1 removed" in summary
    assert not Player.objects.filter(tm_id=607720).exists()


def test_fetch_fills_the_cache_from_recorded_pages_then_ingests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_command: Callable[..., str]
) -> None:
    requested: list[str] = []

    def recorded_response(url: str) -> str:
        requested.append(url)
        if "wettbewerb/L1" in url:
            return recorded_page("tm_league_2025.html.gz")
        return recorded_page("tm_squad_bayern.html.gz")

    monkeypatch.setattr(tm_scrape, "polite_fetch", recorded_response)
    cache = tmp_path / "tm_cache"

    summary = run_command("scrape_transfermarkt", cache_dir=str(cache))

    assert len(requested) == 1 + 18
    assert (cache / "league_2025.html").exists()
    assert (cache / f"squad_{HEIDENHEIM_TM_ID}.html").exists()
    # Every squad page is the Bayern one, so the club with the lowest tm id claims all players.
    assert summary.startswith("scrape_transfermarkt: 18 teams linked, 40 players")
    claimants = set(Player.objects.values_list("team__tm_id", flat=True))
    assert claimants == {Team.objects.exclude(tm_id=None).order_by("tm_id").first().tm_id}  # type: ignore[union-attr]
