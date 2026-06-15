"""Tests for football-data.co.uk CSV parsing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from bundespredict.data.parse import MatchRow, parse_match_csv, season_from_path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "D1_9999.csv"


@pytest.fixture
def rows() -> list[MatchRow]:
    return parse_match_csv(FIXTURE)


def test_season_derived_from_filename() -> None:
    assert season_from_path(FIXTURE) == "9999"


def test_unplayed_rows_are_skipped(rows: list[MatchRow]) -> None:
    # 3 data rows, but the Mainz–Freiburg row has blank scores (postponed).
    assert len(rows) == 2
    pairs = {(r.home_team, r.away_team) for r in rows}
    assert ("Mainz", "Freiburg") not in pairs


def test_played_row_fields_are_coerced(rows: list[MatchRow]) -> None:
    row = rows[0]
    assert row.season == "9999"
    assert row.date == date(2023, 8, 18)
    assert row.home_team == "Dortmund"
    assert row.away_team == "FC Koln"
    assert (row.home_goals, row.away_goals, row.ftr) == (2, 1, "H")
    assert isinstance(row.home_goals, int)
    assert (row.ht_home_goals, row.ht_away_goals, row.htr) == (1, 0, "H")
    assert row.home_shots == 15
    assert row.away_corners == 4
    assert row.b365_home == pytest.approx(1.50)
    assert row.avg_away == pytest.approx(5.80)


def test_blank_optional_fields_become_none(rows: list[MatchRow]) -> None:
    # Bayern–Leverkusen: scores present, every stat/odds column blank.
    row = rows[1]
    assert (row.home_goals, row.away_goals, row.ftr) == (3, 3, "D")
    assert row.home_shots is None
    assert row.away_shots is None
    assert row.home_yellows is None
    assert row.b365_home is None
    assert row.avg_draw is None
    assert row.htr == "A"


def test_scores_are_never_none(rows: list[MatchRow]) -> None:
    for row in rows:
        assert row.home_goals is not None
        assert row.away_goals is not None
        assert row.ftr in {"H", "D", "A"}


def test_bad_date_raises(tmp_path: Path) -> None:
    bad = tmp_path / "D1_9998.csv"
    bad.write_text(
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nnot-a-date,Dortmund,Mainz,1,0,H\n",
        encoding="latin-1",
    )
    with pytest.raises(ValueError, match="date"):
        parse_match_csv(bad)
