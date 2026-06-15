"""Shrinkage for low-history teams (the August problem).

Every season ~3 promoted teams arrive with little or no top-flight history. Early
on, their fitted attack/defense swing wildly on a handful of results, so the
model spits out garbage predictions for them. The fix is empirical-Bayes
shrinkage: pull each team's estimate toward the league mean by an amount that
depends on how much evidence backs it. A team with many matches keeps its fitted
strength; a team with almost none is dragged back to average.

Under our sum-to-zero gauge the league mean is exactly 0, so "shrink toward the
mean" is "scale toward 0" by ``n / (n + k)``, where ``n`` is the team's match
count and ``k`` is the pseudo-count at which a team sits halfway. After scaling we
re-center so the gauge (and thus the league-average goal level) is preserved.

Pure: ratings + counts in, ratings out. No I/O.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from bundespredict.model.dixon_coles import MatchData, TeamRatings

# Matches of evidence at which a team's strength is trusted halfway. Roughly a
# quarter-season — enough that a promoted side stops being pulled hard once it
# has played a handful of games. Heuristic; tune on the holdout later.
DEFAULT_SHRINKAGE_K = 10.0


def team_match_counts(data: MatchData) -> NDArray[np.intp]:
    """Matches each team played (home or away), aligned to the team index."""
    counts = np.zeros(data.n_teams, dtype=np.intp)
    np.add.at(counts, data.home_idx, 1)
    np.add.at(counts, data.away_idx, 1)
    return counts


def shrink_ratings(
    ratings: TeamRatings,
    match_counts: NDArray[np.intp],
    *,
    k: float = DEFAULT_SHRINKAGE_K,
) -> TeamRatings:
    """Shrink attack/defense toward the league mean by evidence weight ``n/(n+k)``.

    ``home_adv`` and ``rho`` are league-level, not per-team, so they pass through
    untouched. ``log_likelihood`` is carried over as a diagnostic — it described
    the pre-shrinkage fit and isn't recomputed.
    """
    if match_counts.shape[0] != ratings.attack.shape[0]:
        raise ValueError("match_counts length must match the number of teams")

    weight = match_counts / (match_counts + k)
    attack = ratings.attack * weight
    defense = ratings.defense * weight
    # Re-center to restore sum-to-zero: differential scaling shifts the mean off 0,
    # which would otherwise nudge the whole league's goal level.
    attack = attack - attack.mean()
    defense = defense - defense.mean()

    return TeamRatings(
        teams=ratings.teams,
        attack=attack,
        defense=defense,
        home_adv=ratings.home_adv,
        rho=ratings.rho,
        log_likelihood=ratings.log_likelihood,
    )
