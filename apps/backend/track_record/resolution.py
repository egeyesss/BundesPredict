"""Matching frozen predictions with the results that have been ingested since."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from django.utils import timezone

from football.models import Match

from .models import FixturePrediction, Resolution
from .scoring import AWAY, DRAW, HOME, outcome_index

OUTCOME_LETTERS = {HOME: "H", DRAW: "D", AWAY: "A"}


@dataclass
class ResolveReport:
    resolved: list[Resolution] = field(default_factory=list)
    unresolved: list[FixturePrediction] = field(default_factory=list)


def resolve_predictions(*, now: datetime | None = None) -> ResolveReport:
    """Resolve every frozen prediction whose fixture has a stored result.

    Safe to run any number of times: predictions that already have a resolution are skipped,
    and fixtures without a result are left for a later run.
    """
    now = now if now is not None else timezone.now()
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    pending = list(
        FixturePrediction.objects.filter(resolution__isnull=True)
        .select_related("fixture__home", "fixture__away")
        .order_by("fixture__kickoff_utc", "id")
    )
    seasons = {prediction.fixture.season for prediction in pending}
    results = {
        (match.season, match.home_id, match.away_id): match
        for match in Match.objects.filter(season__in=seasons)
    }

    report = ResolveReport()
    for prediction in pending:
        fixture = prediction.fixture
        match = results.get((fixture.season, fixture.home_id, fixture.away_id))
        if match is None:
            report.unresolved.append(prediction)
            continue
        outcome = outcome_index(match.home_goals, match.away_goals)
        report.resolved.append(
            Resolution.objects.create(
                prediction=prediction,
                home_goals=match.home_goals,
                away_goals=match.away_goals,
                outcome=OUTCOME_LETTERS[outcome],
                resolved_at=now,
            )
        )
    return report
