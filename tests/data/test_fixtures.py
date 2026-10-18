"""Fixtures parsing, from a recorded OpenLigaDB payload."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from bundespredict.data.fixtures import parse_fixtures
from bundespredict.data.seasons import season_code

SAMPLE = Path(__file__).parent / "fixtures" / "openligadb_sample.json"


def _sample_payload() -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return payload


def test_season_code() -> None:
    assert season_code(2026) == "2627"
    assert season_code(2099) == "9900"


def test_parse_recorded_payload() -> None:
    rows = parse_fixtures(_sample_payload(), 2026)
    assert len(rows) == 3
    bayern = next(r for r in rows if r.home == "FC Bayern München")
    assert bayern.away == "VfB Stuttgart"
    assert bayern.season == "2627"
    assert bayern.matchday == 1
    # UTC, naive, with the Z suffix stripped correctly.
    assert bayern.kickoff_utc == datetime(2026, 8, 28, 18, 30)


def test_parse_skips_finished_and_incomplete_entries() -> None:
    payload = _sample_payload()
    payload[0]["matchIsFinished"] = True
    payload[1]["matchDateTimeUTC"] = None
    rows = parse_fixtures(payload, 2026)
    assert len(rows) == 1
    assert rows[0].home == "Borussia Dortmund"
