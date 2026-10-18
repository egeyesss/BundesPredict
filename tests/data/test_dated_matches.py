"""Array building behind the Django training service."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from bundespredict.data.dated_matches import DatedMatches, MatchRecord


def _record(home: str, away: str, day: int, **xg: float) -> MatchRecord:
    return MatchRecord(home, away, 2, 1, date(2024, 8, day), **xg)


def test_teams_are_name_sorted_and_indexed_contiguously() -> None:
    dated = DatedMatches.from_records([_record("Zeta", "Alpha", 1), _record("Beta", "Zeta", 8)])

    assert dated.teams == ("Alpha", "Beta", "Zeta")
    assert dated.home_idx.tolist() == [2, 1]
    assert dated.away_idx.tolist() == [0, 2]
    assert len(dated) == 2


def test_rows_keep_the_order_they_were_given() -> None:
    dated = DatedMatches.from_records([_record("B", "A", 15), _record("A", "B", 1)])

    assert dated.day_ordinal.tolist() == [
        date(2024, 8, 15).toordinal(),
        date(2024, 8, 1).toordinal(),
    ]


def test_missing_xg_becomes_nan_not_zero() -> None:
    dated = DatedMatches.from_records(
        [_record("A", "B", 1, home_xg=1.2, away_xg=0.4), _record("B", "A", 8)]
    )

    assert dated.home_xg[0] == pytest.approx(1.2)
    assert np.isnan(dated.home_xg[1]) and np.isnan(dated.away_xg[1])


def test_no_records_is_an_error() -> None:
    with pytest.raises(ValueError, match="no matches"):
        DatedMatches.from_records([])
