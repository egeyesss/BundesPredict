"""Transfermarkt cache: what gets fetched when, and how the cache reads back.

Pages come from the recorded snapshots, so nothing here touches the network.
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bundespredict.data import tm_scrape

FIXTURES = Path(__file__).parent / "fixtures"
HEIDENHEIM_TM_ID = 2036


def _page(name: str) -> str:
    return gzip.open(FIXTURES / name, "rt", encoding="utf-8").read()


class RecordedSite:
    """Serves the recorded league and squad pages and remembers what was asked for."""

    def __init__(self) -> None:
        self.requested: list[str] = []

    def __call__(self, url: str) -> str:
        self.requested.append(url)
        if "wettbewerb/L1" in url:
            return _page("tm_league_2025.html.gz")
        return _page("tm_squad_heidenheim.html.gz")


@pytest.fixture(autouse=True)
def two_season_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tm_scrape, "FIRST_SEASON", 2024)


def test_first_fetch_gets_every_league_page_and_the_current_squads(tmp_path: Path) -> None:
    site = RecordedSite()

    tm_scrape.fetch_all(tmp_path, 2025, fetch=site)

    league_requests = [u for u in site.requested if "wettbewerb/L1" in u]
    assert [u.rsplit("=", 1)[1] for u in league_requests] == ["2024", "2025"]
    assert len(site.requested) == 2 + 18
    assert (tmp_path / f"squad_{HEIDENHEIM_TM_ID}.html").exists()
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert f"squad_{HEIDENHEIM_TM_ID}.html" in meta


def test_a_second_fetch_only_refreshes_the_current_season(tmp_path: Path) -> None:
    tm_scrape.fetch_all(tmp_path, 2025, fetch=RecordedSite())
    site = RecordedSite()

    tm_scrape.fetch_all(tmp_path, 2025, fetch=site)

    assert not any("saison_id=2024" in u for u in site.requested)
    assert sum("saison_id=2025" in u and "wettbewerb" in u for u in site.requested) == 1
    assert len(site.requested) == 1 + 18


def test_read_cache_parses_the_pages_and_reports_the_oldest_squad_fetch(tmp_path: Path) -> None:
    tm_scrape.fetch_all(tmp_path, 2025, fetch=RecordedSite())
    meta = json.loads((tmp_path / "meta.json").read_text())
    meta[f"squad_{HEIDENHEIM_TM_ID}.html"] = "2025-09-01T03:00:00+00:00"
    (tmp_path / "meta.json").write_text(json.dumps(meta))

    snapshot = tm_scrape.read_cache(tmp_path, 2025)

    assert {club.season for club in snapshot.clubs} == {"2425", "2526"}
    assert len(snapshot.squads) == 18
    assert snapshot.scraped_at == datetime(2025, 9, 1, 3, 0, tzinfo=UTC)


def test_read_cache_skips_pages_that_were_never_fetched(tmp_path: Path) -> None:
    (tmp_path / "league_2025.html").write_text(_page("tm_league_2025.html.gz"), encoding="utf-8")

    snapshot = tm_scrape.read_cache(tmp_path, 2025)

    assert len(snapshot.clubs) == 18
    assert snapshot.squads == {}
    assert snapshot.scraped_at.tzinfo is not None
