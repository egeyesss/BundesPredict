"""Tests for Understat xG parsing.

The parser runs against a committed slice of real ``datesData`` (pinning the
payload shape) and checks that unplayed rows are dropped and names canonicalized.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from bundespredict.data.team_aliases import UnmappedTeamError
from bundespredict.data.understat import parse_understat_season

_FIXTURE = Path(__file__).parent / "fixtures" / "understat_sample.json"


def _payload() -> list[dict[str, Any]]:
    return list(json.loads(_FIXTURE.read_text()))


def test_parse_drops_unplayed_and_canonicalizes() -> None:
    rows = parse_understat_season(_payload(), "2324")
    # Two played matches; the unplayed (isResult false) row is dropped.
    assert len(rows) == 2
    first = rows[0]
    assert first.home == "SV Werder Bremen"  # canonicalized from "Werder Bremen"
    assert first.away == "Bayern Munich"
    assert first.home_xg == 0.63974
    assert first.away_xg == 2.89704
    assert first.date == date(2023, 8, 18)


def test_parse_raises_on_unmapped_team() -> None:
    payload = [
        {
            "id": "9",
            "isResult": True,
            "h": {"title": "Some New Club"},
            "a": {"title": "Bayern Munich"},
            "goals": {"h": "1", "a": "1"},
            "xG": {"h": "1.0", "a": "1.0"},
            "datetime": "2023-08-18 18:30:00",
        }
    ]
    try:
        parse_understat_season(payload, "2324")
    except UnmappedTeamError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected UnmappedTeamError")
