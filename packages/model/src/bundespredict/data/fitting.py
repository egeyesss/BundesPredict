"""Fit-and-shrink step shared by the serving refit and the walk-forward backtest.

Pure: arrays in, ratings out. Reading matches and persisting the result belong to the
caller, so the same recipe runs against the SQLAlchemy session and the Django ORM.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from bundespredict.model.dixon_coles import TeamRatings, fit_dixon_coles
from bundespredict.model.shrinkage import (
    DEFAULT_SHRINKAGE_K,
    ShrinkTargets,
    shrink_ratings,
    team_match_counts,
    value_implied_targets,
)

from .dated_matches import DatedMatches


def fit_shrunk_ratings(
    dated: DatedMatches,
    *,
    xi: float,
    reference: date,
    shrinkage_k: float = DEFAULT_SHRINKAGE_K,
    season_values: dict[str, int] | None = None,
    use_xg: bool = False,
) -> TeamRatings:
    """Time-decayed Dixon-Coles fit with low-history teams shrunk toward a prior.

    ``season_values`` maps canonical team name to squad value in EUR for the season being
    predicted. When given and non-empty, teams are pulled toward what their squad value
    implies instead of the league mean; teams missing from it are treated as unknown.
    """
    data = dated.to_match_data(xi=xi, reference=reference, use_xg=use_xg)
    ratings = fit_dixon_coles(data, use_xg=use_xg)
    counts = team_match_counts(data)
    targets: ShrinkTargets | None = None
    if season_values:
        log_values = np.array(
            [np.log(season_values[t]) if t in season_values else np.nan for t in data.teams],
            dtype=np.float64,
        )
        targets = value_implied_targets(ratings, counts, log_values)
    return shrink_ratings(ratings, counts, k=shrinkage_k, targets=targets)
