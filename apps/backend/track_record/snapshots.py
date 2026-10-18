"""Freezing the base model's prediction for fixtures that have not kicked off yet."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from bundespredict.model.dixon_coles import TeamRatings
from football.models import Fixture, ModelRun
from football.repositories import SERVING_VERSION, latest_model_run, ratings_for

from .models import FixturePrediction

SNAPSHOT_WINDOW = timedelta(hours=48)


class KickoffPassedError(ValueError):
    """The fixture kicks off at or before the clock, so it can no longer be forecast."""


class NoModelRunError(RuntimeError):
    """There is no fitted model to predict with."""


@dataclass
class SnapshotReport:
    created: list[FixturePrediction] = field(default_factory=list)
    skipped_without_ratings: list[Fixture] = field(default_factory=list)


def freeze_fixture(
    fixture: Fixture, *, run: ModelRun, ratings: TeamRatings, now: datetime
) -> FixturePrediction:
    """Store the base prediction of `ratings` (the fit of `run`) for `fixture`.

    Raises `KickoffPassedError` unless the fixture kicks off strictly after `now`, and
    `IntegrityError` if the fixture already has a snapshot.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if fixture.kickoff_utc <= now:
        raise KickoffPassedError(f"{fixture} kicks off at {fixture.kickoff_utc}, not after {now}")

    markets = ratings.predict(fixture.home.name, fixture.away.name)
    return FixturePrediction.objects.create(
        fixture=fixture,
        model_run=run,
        p_home=markets.p_home,
        p_draw=markets.p_draw,
        p_away=markets.p_away,
        exp_home_goals=markets.exp_home_goals,
        exp_away_goals=markets.exp_away_goals,
        score_grid=[list(row) for row in markets.score_grid],
        created_at=now,
    )


def snapshot_upcoming(*, now: datetime | None = None) -> SnapshotReport:
    """Freeze every fixture kicking off within 48 hours of `now` that has no snapshot yet.

    Fixtures with a team the newest serving run has no ratings for are reported instead of frozen.
    """
    now = now if now is not None else timezone.now()
    run = latest_model_run(version=SERVING_VERSION)
    if run is None:
        raise NoModelRunError("no model run has been fitted yet")
    ratings = ratings_for(run)
    known_teams = set(ratings.teams)

    pending = (
        Fixture.objects.filter(
            kickoff_utc__gt=now,
            kickoff_utc__lte=now + SNAPSHOT_WINDOW,
            frozen_prediction__isnull=True,
        )
        .select_related("home", "away")
        .order_by("kickoff_utc", "id")
    )

    report = SnapshotReport()
    for fixture in pending:
        if fixture.home.name not in known_teams or fixture.away.name not in known_teams:
            report.skipped_without_ratings.append(fixture)
            continue
        try:
            # The savepoint keeps a concurrent run's insert from poisoning the outer transaction.
            with transaction.atomic():
                report.created.append(freeze_fixture(fixture, run=run, ratings=ratings, now=now))
        except IntegrityError:
            continue
    return report
