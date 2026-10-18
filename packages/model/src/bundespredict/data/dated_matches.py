"""Match arrays for the pure engine, independent of where the rows came from.

The Django training service turns database rows into :class:`DatedMatches`; the array
building lives here so it needs no database.
Team identifiers are the canonical team names, contiguously indexed over whatever teams
appear in the slice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from bundespredict.model.dixon_coles import MatchData
from bundespredict.model.time_decay import decay_weights
from bundespredict.model.xg_offset import current_team_xg_gaps, rolling_xg_offsets


@dataclass(frozen=True)
class MatchRecord:
    """One played match as the loader hands it over, teams by canonical name."""

    home: str
    away: str
    home_goals: int
    away_goals: int
    played_on: date
    home_xg: float | None = None
    away_xg: float | None = None


@dataclass(frozen=True)
class XgGaps:
    """Per-team pre-match xG gaps (as of a cutoff), keyed by canonical name.

    ``offsets(home, away)`` builds a fixture's ``(home_offset, away_offset)`` the
    same way the training feature does (attack gap of the scorer plus defence
    gap of the opponent), so serving a future fixture matches how the coefficient
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

    @classmethod
    def from_records(cls, records: Sequence[MatchRecord]) -> DatedMatches:
        """Build the arrays from records already in the order the fit should see them.

        Missing xG becomes NaN, so the rolling offset skips it rather than treating a gap in
        coverage as zero xG.
        """
        if not records:
            raise ValueError("no matches matched the given filters")
        teams = tuple(sorted({r.home for r in records} | {r.away for r in records}))
        index = {name: i for i, name in enumerate(teams)}
        return cls(
            teams=teams,
            home_idx=np.array([index[r.home] for r in records], dtype=np.intp),
            away_idx=np.array([index[r.away] for r in records], dtype=np.intp),
            home_goals=np.array([r.home_goals for r in records], dtype=np.intp),
            away_goals=np.array([r.away_goals for r in records], dtype=np.intp),
            day_ordinal=np.array([r.played_on.toordinal() for r in records], dtype=np.intp),
            home_xg=np.array(
                [np.nan if r.home_xg is None else r.home_xg for r in records], dtype=np.float64
            ),
            away_xg=np.array(
                [np.nan if r.away_xg is None else r.away_xg for r in records], dtype=np.float64
            ),
        )
