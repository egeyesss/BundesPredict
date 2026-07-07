"""Tests for the pre-match rolling-xG offset builder.

The load-bearing property is leakage safety: a match's offset must be built only
from strictly-earlier matches. The rest pin the gap composition and NaN handling.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from bundespredict.model.xg_offset import rolling_xg_offsets


def _offsets(
    home_idx: Sequence[int],
    away_idx: Sequence[int],
    home_goals: Sequence[int],
    away_goals: Sequence[int],
    home_xg: Sequence[float],
    away_xg: Sequence[float],
    days: Sequence[int],
    n_teams: int,
    xi: float = 0.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    return rolling_xg_offsets(
        np.array(home_idx, dtype=np.intp),
        np.array(away_idx, dtype=np.intp),
        np.array(home_goals, dtype=np.intp),
        np.array(away_goals, dtype=np.intp),
        np.array(home_xg, dtype=np.float64),
        np.array(away_xg, dtype=np.float64),
        np.array(days, dtype=np.intp),
        n_teams,
        xi=xi,
    )


def test_first_match_of_a_team_has_zero_offset() -> None:
    # Two teams, one match: neither has any prior history.
    home_off, away_off = _offsets(
        home_idx=[0],
        away_idx=[1],
        home_goals=[1],
        away_goals=[1],
        home_xg=[2.0],
        away_xg=[0.5],
        days=[10],
        n_teams=2,
    )
    assert home_off[0] == 0.0
    assert away_off[0] == 0.0


def test_offset_uses_only_strictly_earlier_matches() -> None:
    # Team 0 plays match 0 (home, xG 2.0 vs 1 goal -> for-gap +1.0), then match 1.
    # Match 1's home offset must reflect match 0's gap, not match 1's own xG.
    home_off, away_off = _offsets(
        home_idx=[0, 0],
        away_idx=[1, 2],
        home_goals=[1, 0],
        away_goals=[1, 0],
        home_xg=[2.0, 9.9],  # match 1 own xG is huge but must not leak in
        away_xg=[1.0, 1.0],
        days=[10, 20],
        n_teams=3,
    )
    assert home_off[0] == 0.0  # first match for team 0
    # Match 1: team 0 attack gap = (2.0 - 1) = 1.0 from match 0; team 2 has no
    # history so its defence gap is 0 -> home offset is exactly 1.0.
    assert home_off[1] == 1.0


def test_offset_combines_attack_and_defence_gaps() -> None:
    # Round 1: team0 home vs team1; team2 home vs team3. Round 2: team0 vs team2.
    # team0 for-gap from R1 = home_xg-home_goals; team2 against-gap from R1 =
    # (their away? no, they were home) home... build it so the sum is checkable.
    home_off, _ = _offsets(
        home_idx=[0, 2, 0],
        away_idx=[1, 3, 2],
        home_goals=[0, 1, 0],
        away_goals=[0, 0, 0],
        home_xg=[1.5, 1.0, 0.0],  # team0 R1 for-gap = 1.5
        away_xg=[0.0, 2.0, 0.0],  # team2 R1 conceded xG 2.0, goals 0 -> against-gap 2.0
        days=[10, 10, 20],
        n_teams=4,
    )
    # Match 2 (team0 home vs team2): team0 attack gap 1.5 + team2 defence gap 2.0.
    assert home_off[2] == 3.5


def test_nan_xg_is_skipped_in_the_rolling_mean() -> None:
    # Team 0's first match has no xG (NaN); its gap must be ignored, so the third
    # match sees only the second match's gap rather than a NaN-poisoned mean.
    home_off, _ = _offsets(
        home_idx=[0, 0, 0],
        away_idx=[1, 2, 3],
        home_goals=[0, 1, 0],
        away_goals=[0, 0, 0],
        home_xg=[np.nan, 2.0, 0.0],  # match 0 xG missing, match 1 for-gap = 1.0
        away_xg=[0.0, 0.0, 0.0],
        days=[10, 20, 30],
        n_teams=4,
    )
    assert home_off[0] == 0.0
    assert home_off[1] == 0.0  # only prior match (0) had NaN -> no valid history
    assert home_off[2] == 1.0  # mean of {match0: skipped, match1: +1.0} = 1.0
