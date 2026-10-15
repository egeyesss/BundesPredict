"""DB -> arrays bridge for the pure model engine.

The engine in ``model/`` never touches the database. This loader is the seam:
it pulls match rows into plain integer-indexed numpy arrays and hands them over
as :class:`~bundespredict.model.dixon_coles.MatchData`. Team identifiers are the
canonical team names, contiguously indexed over whatever teams appear in the
queried slice.

Leakage discipline is built in from day one: ``as_of_date`` filters to matches
played **strictly before** it, so a fit for a fixture on date D only ever sees
results that were known before kickoff. Walk-forward backtesting (Phase 3) just
calls this repeatedly with a moving ``as_of_date``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.model.dixon_coles import MatchData
from bundespredict.model.time_decay import decay_weights
from bundespredict.model.xg_offset import current_team_xg_gaps, rolling_xg_offsets

from .models import Match, Team


@dataclass(frozen=True)
class XgGaps:
    """Per-team pre-match xG gaps (as of a cutoff), keyed by canonical name.

    ``offsets(home, away)`` builds a fixture's ``(home_offset, away_offset)`` the
    same way the training feature does — attack gap of the scorer plus defence
    gap of the opponent — so serving a future fixture matches how the coefficient
    was fit. Unknown teams contribute 0 (neutral).
    """

    att_gap: dict[str, float]
    def_gap: dict[str, float]

    def offsets(self, home: str, away: str) -> tuple[float, float]:
        home_offset = self.att_gap.get(home, 0.0) + self.def_gap.get(away, 0.0)
        away_offset = self.att_gap.get(away, 0.0) + self.def_gap.get(home, 0.0)
        return home_offset, away_offset


@dataclass(frozen=True)
class DatedMatches:
    """Match arrays plus each match's date ordinal, before any time-weighting.

    Keeping the dates lets time-decay weighting and xi-selection re-weight the
    same rows without another database round trip. ``day_ordinal`` is
    ``date.toordinal()`` (days since year 1), so day differences are plain
    integer subtraction.
    """

    teams: tuple[str, ...]
    home_idx: NDArray[np.intp]
    away_idx: NDArray[np.intp]
    home_goals: NDArray[np.intp]
    away_goals: NDArray[np.intp]
    day_ordinal: NDArray[np.intp]
    # Per-match xG (NaN where a match has no Understat coverage). Feeds the
    # rolling pre-match offset; never used un-rolled (that would be leakage).
    home_xg: NDArray[np.float64]
    away_xg: NDArray[np.float64]

    def __len__(self) -> int:
        return len(self.home_idx)

    def xg_gaps(self, *, xi: float = 0.0, reference: date | None = None) -> XgGaps:
        """Each team's decayed xG gaps as of ``reference`` (default: latest match).

        Used to build offsets for a *future* fixture (one not in this window),
        which is what serving and the backtest's prediction step need.
        """
        ref_ordinal = (
            reference.toordinal() if reference is not None else int(self.day_ordinal.max())
        )
        att, dfn = current_team_xg_gaps(
            self.home_idx,
            self.away_idx,
            self.home_goals,
            self.away_goals,
            self.home_xg,
            self.away_xg,
            self.day_ordinal,
            len(self.teams),
            xi=xi,
            reference_day=ref_ordinal,
        )
        return XgGaps(
            att_gap={t: float(att[i]) for i, t in enumerate(self.teams)},
            def_gap={t: float(dfn[i]) for i, t in enumerate(self.teams)},
        )

    def to_match_data(
        self, *, xi: float = 0.0, reference: date | None = None, use_xg: bool = False
    ) -> MatchData:
        """Apply exponential time decay and return engine-ready ``MatchData``.

        Each match is weighted by ``exp(-xi * days_before)`` where ``days_before``
        is measured back from ``reference`` (default: the most recent match in the
        set, so the newest match gets weight ~1). ``xi == 0`` gives uniform
        weights. With ``use_xg`` the pre-match rolling-xG offsets are computed
        (decayed with the same ``xi``) and attached so the fit can estimate the
        xG coefficient.
        """
        if len(self) == 0:
            raise ValueError("no matches to build MatchData from")
        ref_ordinal = (
            reference.toordinal() if reference is not None else int(self.day_ordinal.max())
        )
        days_before = (ref_ordinal - self.day_ordinal).astype(np.float64)
        home_offset = away_offset = None
        if use_xg:
            home_offset, away_offset = rolling_xg_offsets(
                self.home_idx,
                self.away_idx,
                self.home_goals,
                self.away_goals,
                self.home_xg,
                self.away_xg,
                self.day_ordinal,
                len(self.teams),
                xi=xi,
            )
        return MatchData(
            teams=self.teams,
            home_idx=self.home_idx,
            away_idx=self.away_idx,
            home_goals=self.home_goals,
            away_goals=self.away_goals,
            weights=decay_weights(days_before, xi),
            home_offset=home_offset,
            away_offset=away_offset,
        )


def load_dated_matches(
    session: Session,
    *,
    as_of_date: date | None = None,
    seasons: Sequence[str] | None = None,
) -> DatedMatches:
    """Pull matches into arrays, optionally filtered for leakage and by season.

    Only matches played strictly before ``as_of_date`` are returned (when given),
    so nothing from on/after the prediction date can leak into a fit. Teams are
    indexed over exactly the clubs that appear in the returned slice.
    """
    stmt = (
        select(
            Match.home_id,
            Match.away_id,
            Match.home_goals,
            Match.away_goals,
            Match.date,
            Match.home_xg,
            Match.away_xg,
        )
        .join(Team, Team.id == Match.home_id)
        .order_by(Match.date, Match.id)
    )
    if as_of_date is not None:
        stmt = stmt.where(Match.date < as_of_date)
    if seasons is not None:
        stmt = stmt.where(Match.season.in_(seasons))

    rows = session.execute(stmt).all()
    if not rows:
        raise ValueError("no matches matched the given filters")

    # Map the team ids present in this slice to a contiguous index space, keyed by
    # canonical name (what the engine, agent, and UI all refer to teams by).
    team_ids = {row[0] for row in rows} | {row[1] for row in rows}
    id_to_name: dict[int, str] = dict(
        session.execute(select(Team.id, Team.name).where(Team.id.in_(team_ids))).tuples().all()
    )
    teams = tuple(sorted(id_to_name.values()))
    name_to_index = {name: i for i, name in enumerate(teams)}
    id_to_index = {tid: name_to_index[id_to_name[tid]] for tid in team_ids}

    home_idx = np.array([id_to_index[r[0]] for r in rows], dtype=np.intp)
    away_idx = np.array([id_to_index[r[1]] for r in rows], dtype=np.intp)
    home_goals = np.array([r[2] for r in rows], dtype=np.intp)
    away_goals = np.array([r[3] for r in rows], dtype=np.intp)
    day_ordinal = np.array([r[4].toordinal() for r in rows], dtype=np.intp)
    # Missing xG -> NaN, so the rolling offset skips it rather than treating a
    # gap in coverage as zero xG.
    home_xg = np.array([np.nan if r[5] is None else r[5] for r in rows], dtype=np.float64)
    away_xg = np.array([np.nan if r[6] is None else r[6] for r in rows], dtype=np.float64)

    return DatedMatches(
        teams=teams,
        home_idx=home_idx,
        away_idx=away_idx,
        home_goals=home_goals,
        away_goals=away_goals,
        day_ordinal=day_ordinal,
        home_xg=home_xg,
        away_xg=away_xg,
    )


def load_match_data(
    session: Session,
    *,
    as_of_date: date | None = None,
    seasons: Sequence[str] | None = None,
    xi: float = 0.0,
    use_xg: bool = False,
) -> MatchData:
    """One-shot convenience: load matches and apply time decay in a single call."""
    dated = load_dated_matches(session, as_of_date=as_of_date, seasons=seasons)
    return dated.to_match_data(xi=xi, reference=as_of_date, use_xg=use_xg)
