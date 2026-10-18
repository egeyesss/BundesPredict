"""Scores the squad-value shrinkage prior on the matches it is meant to change.

The prior only moves predictions where evidence is thin, so a whole-backtest RPS comparison would
drown the effect in ~1800 matches that barely change. The slice that matters is each promoted
team's first matches of its first season back up.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from bundespredict.eval.backtest import BacktestResult
from bundespredict.eval.metrics import score_forecast
from football.models import SquadValue

from .backtest import run_walk_forward

EARLY_MATCHES = 6


@dataclass(frozen=True)
class PriorScore:
    label: str
    slice_rps: float
    slice_log_loss: float
    overall_rps: float


@dataclass(frozen=True)
class PromotedPriorReport:
    early_matches: int
    predictions: int
    scores: tuple[PriorScore, ...]


def promoted_early_mask(
    result: BacktestResult, early_matches: int = EARLY_MATCHES
) -> NDArray[np.bool_]:
    """Rows involving a promoted team within its first `early_matches` predicted games.

    Promoted means present in season S and absent from S-1, so the first season in the data has
    no predecessor and contributes nothing.
    """
    teams_by_season: dict[str, set[str]] = defaultdict(set)
    for season, home, away in zip(result.seasons, result.home, result.away, strict=True):
        teams_by_season[season] |= {home, away}

    seasons = sorted(teams_by_season)
    promoted = {
        (current, team)
        for previous, current in zip(seasons, seasons[1:], strict=False)
        for team in teams_by_season[current] - teams_by_season[previous]
    }

    seen: dict[tuple[str, str], int] = defaultdict(int)
    mask = np.zeros(len(result), dtype=np.bool_)
    order = np.argsort(
        np.array([d.toordinal() for d in result.dates], dtype=np.intp), kind="stable"
    )
    for i in order:
        for team in (result.home[i], result.away[i]):
            key = (result.seasons[i], team)
            if key in promoted and seen[key] < early_matches:
                seen[key] += 1
                mask[i] = True
    return mask


def evaluate_promoted_prior(*, xi: float, min_train_matches: int) -> PromotedPriorReport:
    """Run the walk-forward with the league-mean and the value-implied prior and score both."""
    if not SquadValue.objects.exists():
        raise ValueError("no squad values stored; run scrape_transfermarkt first")

    runs = (
        ("league-mean prior", False),
        ("value-implied prior", True),
    )
    results = [
        (
            label,
            run_walk_forward(
                xi=xi,
                min_train_matches=min_train_matches,
                store=None,
                use_squad_values=use_values,
            ),
        )
        for label, use_values in runs
    ]

    base = results[0][1]
    if any(r.home != base.home or r.dates != base.dates for _, r in results):
        raise AssertionError("backtest rows diverged between the two priors")
    mask = promoted_early_mask(base)

    scores = []
    for label, result in results:
        in_slice = score_forecast(result.model_probs[mask], result.outcomes[mask])
        overall = score_forecast(result.model_probs, result.outcomes)
        scores.append(PriorScore(label, in_slice.rps, in_slice.log_loss, overall.rps))
    return PromotedPriorReport(int(mask.sum()), len(base), tuple(scores))
