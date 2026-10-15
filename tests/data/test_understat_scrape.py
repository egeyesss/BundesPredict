"""Understat cache writer: a failed season must not lose the others."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bundespredict.data.understat_scrape import cache_path, scrape_seasons

_PAYLOAD = [{"id": "1", "isResult": True}]


def test_each_season_lands_in_its_own_file_with_metadata(tmp_path: Path) -> None:
    scraped = scrape_seasons(tmp_path, [2023, 2024], fetch=lambda year: _PAYLOAD, pause=0)

    assert scraped == {"2324": 1, "2425": 1}
    assert json.loads(cache_path(tmp_path, 2023).read_text()) == _PAYLOAD
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["2425"]["matches"] == 1


def test_a_blocked_season_is_skipped_and_the_rest_are_kept(tmp_path: Path) -> None:
    def fetch(year: int) -> list[dict[str, Any]]:
        if year == 2023:
            raise TimeoutError("cloudflare challenge")
        return _PAYLOAD

    scraped = scrape_seasons(tmp_path, [2023, 2024], fetch=fetch, pause=0)

    assert scraped == {"2425": 1}
    assert not cache_path(tmp_path, 2023).exists()
