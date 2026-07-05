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

The league mean is a crude prior, though: a promoted Hamburger SV with a €180m
squad is not an average newcomer. With squad market values available (the
Transfermarkt scrape), :func:`value_implied_targets` builds a better shrink
destination — regress the *well-estimated* teams' attack/defense on log squad
value, then read every team's target off that line. Low-evidence teams get
pulled toward what their squad value implies instead of toward 0; teams without
a value fall back to the league mean. Same evidence weighting either way.

Pure: ratings + counts (+ optional value array) in, ratings out. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class ShrinkTargets:
    """Per-team shrink destinations, aligned to the ratings' team index."""

    attack: NDArray[np.float64]
    defense: NDArray[np.float64]


def shrink_ratings(
    ratings: TeamRatings,
    match_counts: NDArray[np.intp],
    *,
    k: float = DEFAULT_SHRINKAGE_K,
    targets: ShrinkTargets | None = None,
) -> TeamRatings:
    """Shrink attack/defense toward a prior by evidence weight ``n/(n+k)``.

    Without ``targets`` the prior is the league mean (0 in our gauge), i.e. the
    original behavior. With ``targets`` each team is pulled toward its own
    destination: ``w * fitted + (1 - w) * target``. ``home_adv`` and ``rho`` are
    league-level, not per-team, so they pass through untouched;
    ``log_likelihood`` is carried over as a diagnostic — it described the
    pre-shrinkage fit and isn't recomputed.
    """
    if match_counts.shape[0] != ratings.attack.shape[0]:
        raise ValueError("match_counts length must match the number of teams")
    if targets is not None and (
        targets.attack.shape != ratings.attack.shape
        or targets.defense.shape != ratings.defense.shape
    ):
        raise ValueError("targets must align with the ratings' team index")

    weight = match_counts / (match_counts + k)
    target_attack = targets.attack if targets is not None else 0.0
    target_defense = targets.defense if targets is not None else 0.0
    attack = ratings.attack * weight + (1.0 - weight) * target_attack
    defense = ratings.defense * weight + (1.0 - weight) * target_defense
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


def _regress_targets(
    fitted: NDArray[np.float64],
    log_values: NDArray[np.float64],
    trusted: NDArray[np.bool_],
) -> NDArray[np.float64]:
    """OLS of ``fitted`` on centered log value over trusted teams, predicted for all.

    Teams without a value (NaN) get target 0 — the league mean, exactly the old
    prior — so a partial value table degrades gracefully.
    """
    has_value = np.isfinite(log_values)
    fit_mask = trusted & has_value
    targets = np.zeros_like(fitted)
    if fit_mask.sum() < 3:  # not enough teams to draw a line through
        return targets
    x = log_values[fit_mask] - log_values[fit_mask].mean()
    if np.allclose(x, 0.0):  # all equal values: slope undefined, fall back to mean
        return targets
    slope = float(x @ fitted[fit_mask] / (x @ x))
    intercept = float(fitted[fit_mask].mean())
    centered = log_values - log_values[fit_mask].mean()
    targets[has_value] = intercept + slope * centered[has_value]
    return targets


def value_implied_targets(
    ratings: TeamRatings,
    match_counts: NDArray[np.intp],
    log_squad_values: NDArray[np.float64],
    *,
    min_matches: int = 20,
) -> ShrinkTargets:
    """Shrink destinations implied by squad market value.

    Attack and defense are each regressed on centered log squad value using
    only teams with at least ``min_matches`` of evidence (their fitted
    strengths are trustworthy), then the fitted line predicts a target for
    every team with a value. ``log_squad_values`` is aligned to
    ``ratings.teams`` with NaN where no value is known — those teams (and
    everyone, when fewer than 3 trusted teams exist) target the league mean,
    which reproduces plain shrinkage.
    """
    if log_squad_values.shape != ratings.attack.shape:
        raise ValueError("log_squad_values must align with the ratings' team index")
    trusted = match_counts >= min_matches
    return ShrinkTargets(
        attack=_regress_targets(ratings.attack, log_squad_values, trusted),
        defense=_regress_targets(ratings.defense, log_squad_values, trusted),
    )
