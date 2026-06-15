"""Postgres-backed tests for the DB -> arrays loader, incl. leakage filtering."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy.orm import Session

from bundespredict.data.loader import load_dated_matches, load_match_data
from bundespredict.data.models import Match, Team


def _seed(session: Session) -> None:
    """Three teams, three matches across two dates (one in 2023, two in 2024)."""
    a = Team(name="Alpha")
    b = Team(name="Beta")
    c = Team(name="Gamma")
    session.add_all([a, b, c])
    session.flush()  # assign ids

    session.add_all(
        [
            Match(
                season="2324",
                date=date(2023, 8, 1),
                home_id=a.id,
                away_id=b.id,
                home_goals=2,
                away_goals=1,
                ftr="H",
            ),
            Match(
                season="2324",
                date=date(2024, 5, 1),
                home_id=b.id,
                away_id=c.id,
                home_goals=0,
                away_goals=0,
                ftr="D",
            ),
            Match(
                season="2324",
                date=date(2024, 5, 10),
                home_id=c.id,
                away_id=a.id,
                home_goals=1,
                away_goals=3,
                ftr="A",
            ),
        ]
    )
    session.commit()


def test_loads_all_matches_and_indexes_teams(session: Session) -> None:
    _seed(session)
    dated = load_dated_matches(session)
    assert len(dated) == 3
    # Teams are sorted canonical names over the slice.
    assert dated.teams == ("Alpha", "Beta", "Gamma")
    # Ordered by date: first match is Alpha(0) vs Beta(1).
    assert dated.home_idx[0] == 0
    assert dated.away_idx[0] == 1
    assert dated.home_goals[0] == 2
    assert dated.away_goals[0] == 1


def test_as_of_date_excludes_on_and_after(session: Session) -> None:
    _seed(session)
    # Cutoff on 2024-05-10 should drop that day's match (strictly-before filter).
    dated = load_dated_matches(session, as_of_date=date(2024, 5, 10))
    assert len(dated) == 2
    # Only Alpha, Beta, Gamma from the first two matches; Gamma appears as away.
    assert set(dated.teams) == {"Alpha", "Beta", "Gamma"}


def test_to_match_data_applies_decay(session: Session) -> None:
    _seed(session)
    dated = load_dated_matches(session)
    md = dated.to_match_data(xi=0.003)
    # Newest match (reference) gets weight ~1; older matches get less.
    assert md.weights.max() == pytest.approx(1.0)
    assert md.weights.min() < 1.0
    # xi=0 -> uniform weights.
    flat = dated.to_match_data(xi=0.0)
    np.testing.assert_allclose(flat.weights, np.ones(3))


def test_load_match_data_threads_as_of_date_as_reference(session: Session) -> None:
    _seed(session)
    md = load_match_data(session, as_of_date=date(2024, 6, 1), xi=0.002)
    assert len(md.home_idx) == 3  # all matches are before the cutoff
    assert md.weights.shape == (3,)


def test_empty_filter_raises(session: Session) -> None:
    _seed(session)
    with pytest.raises(ValueError, match="no matches matched"):
        load_dated_matches(session, as_of_date=date(2000, 1, 1))
