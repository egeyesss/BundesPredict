"""Pre-match rolling-xG offsets: the leakage-safe feature for the log-lambda term.

The Dixon-Coles strengths (alpha/beta) are fit on *goals*. Expected goals carry
extra information — a team that has been out-creating its scoreline tends to
score more going forward (finishing reverts toward xG). This module turns the
per-match xG history into a single pre-match number per side that captures that
residual signal, so the fitter can weigh it with one global coefficient.

The feature is deliberately the **xG-minus-goals gap**, not the xG level: the
level is collinear with the goal-based attack rating, whereas the gap is the part
of xG the goal ratings haven't already absorbed. For each side's scoring
equation the offset sums two decayed trailing means over matches *strictly
before* kickoff:

* the scoring team's ``xG_for - goals_for`` (have they been unlucky in front of
  goal?), and
* the conceding team's ``xG_against - goals_against`` (have they been riding
  good goalkeeping / luck at the back?).

Leakage safety is the whole point and is structural: a match's own xG never
enters its own offset — only strictly-earlier matches do. This is pure array
math with no I/O, so it stays in ``model/`` and is unit-testable.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def _team_trailing_means(
    days: NDArray[np.float64],
    for_gap: NDArray[np.float64],
    against_gap: NDArray[np.float64],
    xi: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Decayed trailing means of one team's for/against gaps, as of each match.

    ``days`` are ascending match-day ordinals for a single team. For match ``k``
    the mean weights every earlier match ``j`` by ``exp(-xi * (day_k - day_j))``;
    a match with no prior history gets 0 (neutral). NaN gaps (a match missing xG)
    are skipped, so a gap in coverage doesn't poison the average.
    """
    n = len(days)
    att = np.zeros(n)
    dfn = np.zeros(n)
    for k in range(n):
        prior = days[:k] < days[k]  # strictly before -> the leakage guarantee
        if not prior.any():
            continue
        w = np.exp(-xi * (days[k] - days[:k])) * prior
        att[k] = _weighted_nanmean(for_gap[:k], w)
        dfn[k] = _weighted_nanmean(against_gap[:k], w)
    return att, dfn


def _weighted_nanmean(values: NDArray[np.float64], weights: NDArray[np.float64]) -> float:
    """Weighted mean ignoring NaN entries; 0.0 when nothing valid remains."""
    valid = ~np.isnan(values)
    w = weights * valid
    total = w.sum()
    if total <= 0.0:
        return 0.0
    return float(np.nansum(values * w) / total)


def rolling_xg_offsets(
    home_idx: NDArray[np.intp],
    away_idx: NDArray[np.intp],
    home_goals: NDArray[np.intp],
    away_goals: NDArray[np.intp],
    home_xg: NDArray[np.float64],
    away_xg: NDArray[np.float64],
    day_ordinal: NDArray[np.intp],
    n_teams: int,
    *,
    xi: float = 0.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Per-match pre-match xG offsets for the home and away scoring equations.

    Matches must be in non-descending date order (the loader guarantees it). xG
    arrays may contain NaN for matches without coverage. Returns two float arrays
    aligned to the input matches:

    * ``home_offset[i] = att_gap(home) + def_gap(away)`` (as of match ``i``)
    * ``away_offset[i] = att_gap(away) + def_gap(home)``

    where the gaps are the decayed trailing means built strictly from earlier
    matches, so nothing from match ``i`` (or later) can leak into its own offset.
    """
    n = len(home_idx)
    days = day_ordinal.astype(np.float64)

    # Per-team trailing gap means, indexed back to the global match rows. att[t]
    # and dfn[t] hold, for each of team t's matches, the value as of that match.
    att_at: dict[int, NDArray[np.float64]] = {}
    dfn_at: dict[int, NDArray[np.float64]] = {}
    rows_of: dict[int, NDArray[np.intp]] = {}

    for t in range(n_teams):
        is_home = home_idx == t
        is_away = away_idx == t
        rows = np.flatnonzero(is_home | is_away)
        if len(rows) == 0:
            continue
        # This team's for/against xG gap in each of its matches (home or away).
        for_gap = np.where(
            is_home[rows],
            home_xg[rows] - home_goals[rows],
            away_xg[rows] - away_goals[rows],
        )
        against_gap = np.where(
            is_home[rows],
            away_xg[rows] - away_goals[rows],
            home_xg[rows] - home_goals[rows],
        )
        att, dfn = _team_trailing_means(days[rows], for_gap, against_gap, xi)
        att_at[t] = att
        dfn_at[t] = dfn
        rows_of[t] = rows

    # Scatter the per-team, per-occurrence values back onto global match rows.
    att_home = np.zeros(n)
    dfn_home = np.zeros(n)
    att_away = np.zeros(n)
    dfn_away = np.zeros(n)
    for t in range(n_teams):
        if t not in rows_of:
            continue
        rows = rows_of[t]
        home_here = home_idx[rows] == t
        att_home[rows[home_here]] = att_at[t][home_here]
        dfn_home[rows[home_here]] = dfn_at[t][home_here]
        away_here = ~home_here
        att_away[rows[away_here]] = att_at[t][away_here]
        dfn_away[rows[away_here]] = dfn_at[t][away_here]

    home_offset = att_home + dfn_away  # home attack gap + away defence gap
    away_offset = att_away + dfn_home  # away attack gap + home defence gap
    return home_offset, away_offset


def current_team_xg_gaps(
    home_idx: NDArray[np.intp],
    away_idx: NDArray[np.intp],
    home_goals: NDArray[np.intp],
    away_goals: NDArray[np.intp],
    home_xg: NDArray[np.float64],
    away_xg: NDArray[np.float64],
    day_ordinal: NDArray[np.intp],
    n_teams: int,
    *,
    xi: float,
    reference_day: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Each team's decayed for/against xG gaps as of ``reference_day``.

    This is the rolling feature evaluated once, "as of now", so it can build the
    offset for a *future* fixture not in the history:
    ``home_offset = att_gap[home] + def_gap[away]`` and symmetrically for away.
    Matches decay relative to ``reference_day`` (typically the prediction cutoff);
    a team with no matches gets 0. Same NaN-skipping as the training builder.
    """
    att_gap = np.zeros(n_teams)
    def_gap = np.zeros(n_teams)
    for t in range(n_teams):
        is_home = home_idx == t
        rows = np.flatnonzero(is_home | (away_idx == t))
        if len(rows) == 0:
            continue
        home_here = is_home[rows]
        for_gap = np.where(
            home_here, home_xg[rows] - home_goals[rows], away_xg[rows] - away_goals[rows]
        )
        against_gap = np.where(
            home_here, away_xg[rows] - away_goals[rows], home_xg[rows] - home_goals[rows]
        )
        w = np.exp(-xi * (reference_day - day_ordinal[rows].astype(np.float64)))
        att_gap[t] = _weighted_nanmean(for_gap, w)
        def_gap[t] = _weighted_nanmean(against_gap, w)
    return att_gap, def_gap
