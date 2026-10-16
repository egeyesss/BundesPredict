from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from django.core.management.base import CommandError

from bundespredict.data import understat_scrape
from bundespredict.data.team_aliases import UNDERSTAT_ALIASES
from football.models import Match

pytestmark = pytest.mark.django_db

UNDERSTAT_TITLE = {canonical: title for title, canonical in UNDERSTAT_ALIASES.items()}


def understat_entry(match: Match, home_xg: float, away_xg: float) -> dict[str, Any]:
    return {
        "id": str(match.pk),
        "isResult": True,
        "h": {"title": UNDERSTAT_TITLE[match.home.name]},
        "a": {"title": UNDERSTAT_TITLE[match.away.name]},
        "xG": {"h": str(home_xg), "a": str(away_xg)},
        "datetime": f"{match.date} 15:30:00",
    }


@pytest.fixture
def season_payload(loaded_results: Path) -> list[dict[str, Any]]:
    season_matches = Match.objects.select_related("home", "away").filter(season="2324")
    matches = list(season_matches.order_by("date", "id")[:2])
    return [understat_entry(matches[0], 1.85, 0.62), understat_entry(matches[1], 0.9, 1.4)]


@pytest.fixture
def cache_dir(tmp_path: Path, season_payload: list[dict[str, Any]]) -> Path:
    directory = tmp_path / "understat_cache"
    directory.mkdir()
    (directory / "bundesliga_2324.json").write_text(json.dumps(season_payload))
    return directory


def test_ingest_from_cache_backfills_xg(cache_dir: Path, run_command: Callable[..., str]) -> None:
    summary = run_command("scrape_understat", skip_fetch=True, cache_dir=str(cache_dir))

    assert summary == (
        "scrape_understat: cached 0 seasons; 1 seasons ingested, 2 parsed, 2 matched, "
        "0 unmatched, 2 updated"
    )
    filled = Match.objects.exclude(home_xg=None).order_by("date", "id")
    assert [(m.home_xg, m.away_xg) for m in filled] == [(1.85, 0.62), (0.9, 1.4)]


def test_second_run_changes_no_rows(
    cache_dir: Path,
    run_command: Callable[..., str],
    table_rows: Callable[[Any], list[tuple[object, ...]]],
) -> None:
    run_command("scrape_understat", skip_fetch=True, cache_dir=str(cache_dir))
    before = table_rows(Match)

    summary = run_command("scrape_understat", skip_fetch=True, cache_dir=str(cache_dir))

    assert summary.endswith("2 matched, 0 unmatched, 0 updated")
    assert table_rows(Match) == before


def test_a_row_without_a_match_is_counted_not_inserted(
    cache_dir: Path, season_payload: list[dict[str, Any]], run_command: Callable[..., str]
) -> None:
    stranger = {**season_payload[0], "datetime": "2023-08-19 15:30:00"}
    stranger["h"] = {"title": "Freiburg"}
    stranger["a"] = {"title": "Freiburg"}
    (cache_dir / "bundesliga_2324.json").write_text(json.dumps([*season_payload, stranger]))
    matches_before = Match.objects.count()

    summary = run_command("scrape_understat", skip_fetch=True, cache_dir=str(cache_dir))

    assert "1 unmatched" in summary
    assert Match.objects.count() == matches_before


def test_fetch_caches_the_recorded_response_then_ingests(
    tmp_path: Path,
    season_payload: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    run_command: Callable[..., str],
) -> None:
    requested: list[int] = []

    def recorded_response(start_year: int, *, headless: bool) -> list[dict[str, Any]]:
        requested.append(start_year)
        return season_payload

    monkeypatch.setattr(understat_scrape, "fetch_season", recorded_response)
    monkeypatch.setattr(understat_scrape, "REQUEST_GAP_SECONDS", 0)
    cache = tmp_path / "understat_cache"

    summary = run_command("scrape_understat", seasons=[2023], cache_dir=str(cache), headless=True)

    assert requested == [2023]
    assert json.loads((cache / "bundesliga_2324.json").read_text()) == season_payload
    assert summary.startswith("scrape_understat: cached 1 seasons; 1 seasons ingested")


def test_a_blocked_scrape_is_reported_and_leaves_the_cache_alone(
    cache_dir: Path, monkeypatch: pytest.MonkeyPatch, run_command: Callable[..., str]
) -> None:
    def blocked(start_year: int, *, headless: bool) -> list[dict[str, Any]]:
        raise TimeoutError("cloudflare challenge")

    monkeypatch.setattr(understat_scrape, "fetch_season", blocked)
    before = (cache_dir / "bundesliga_2324.json").read_text()

    with pytest.raises(CommandError, match="nothing was cached"):
        run_command("scrape_understat", seasons=[2023], cache_dir=str(cache_dir))

    assert (cache_dir / "bundesliga_2324.json").read_text() == before


def test_skip_ingest_only_caches(
    tmp_path: Path,
    season_payload: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    run_command: Callable[..., str],
) -> None:
    monkeypatch.setattr(understat_scrape, "fetch_season", lambda year, *, headless: season_payload)

    summary = run_command(
        "scrape_understat", seasons=[2023], cache_dir=str(tmp_path / "c"), skip_ingest=True
    )

    assert summary == "scrape_understat: cached 1 seasons, ingest skipped"
    assert Match.objects.exclude(home_xg=None).count() == 0
