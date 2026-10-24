from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from itertools import count

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from football.models import Fixture, Match, Team
from track_record.models import FixturePrediction, Resolution
from track_record.resolution import resolve_predictions

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 19, 5, 45, tzinfo=UTC)
FROZEN_AT = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
MakePrediction = Callable[..., FixturePrediction]
AddResult = Callable[..., Match]


@pytest.fixture
def teams(db: None) -> dict[str, Team]:
    return {name: Team.objects.create(name=name) for name in ("Alpha", "Bravo", "Charlie", "Delta")}


@pytest.fixture
def make_prediction(teams: dict[str, Team]) -> MakePrediction:
    from football.models import ModelRun

    run = ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0018,
        rho=-0.1,
        home_adv=0.25,
        log_likelihood=-1.0,
        n_matches=100,
    )
    matchdays = count(1)

    def build(
        home: str, away: str, probs: tuple[float, float, float] = (0.5, 0.3, 0.2)
    ) -> FixturePrediction:
        fixture = Fixture.objects.create(
            season="2627",
            matchday=next(matchdays),
            kickoff_utc=FROZEN_AT + timedelta(days=2),
            home=teams[home],
            away=teams[away],
        )
        grid = [[0.0] * 11 for _ in range(11)]
        return FixturePrediction.objects.create(
            fixture=fixture,
            model_run=run,
            p_home=probs[0],
            p_draw=probs[1],
            p_away=probs[2],
            exp_home_goals=1.5,
            exp_away_goals=1.1,
            score_grid=grid,
            created_at=FROZEN_AT,
        )

    return build


@pytest.fixture
def add_result(teams: dict[str, Team]) -> AddResult:
    def build(home: str, away: str, home_goals: int, away_goals: int) -> Match:
        ftr = "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"
        return Match.objects.create(
            season="2627",
            date=date(2026, 10, 17),
            home=teams[home],
            away=teams[away],
            home_goals=home_goals,
            away_goals=away_goals,
            ftr=ftr,
        )

    return build


class TestResolvePredictions:
    def test_records_the_final_score_and_outcome(
        self, make_prediction: MakePrediction, add_result: AddResult
    ) -> None:
        prediction = make_prediction("Alpha", "Bravo")
        add_result("Alpha", "Bravo", 3, 1)

        report = resolve_predictions(now=NOW)

        resolution = Resolution.objects.get(prediction=prediction)
        assert (resolution.home_goals, resolution.away_goals) == (3, 1)
        assert resolution.outcome == "H"
        assert resolution.resolved_at == NOW
        assert report.resolved == [resolution]

    @pytest.mark.parametrize(("home_goals", "away_goals", "outcome"), [(0, 0, "D"), (1, 2, "A")])
    def test_maps_draws_and_away_wins(
        self,
        make_prediction: MakePrediction,
        add_result: AddResult,
        home_goals: int,
        away_goals: int,
        outcome: str,
    ) -> None:
        make_prediction("Alpha", "Bravo")
        add_result("Alpha", "Bravo", home_goals, away_goals)

        resolve_predictions(now=NOW)

        assert Resolution.objects.get().outcome == outcome

    def test_a_fixture_without_a_result_stays_unresolved(
        self, make_prediction: MakePrediction, add_result: AddResult
    ) -> None:
        make_prediction("Alpha", "Bravo")
        make_prediction("Charlie", "Delta")
        add_result("Alpha", "Bravo", 2, 2)

        report = resolve_predictions(now=NOW)

        assert Resolution.objects.count() == 1
        assert [p.fixture.home.name for p in report.unresolved] == ["Charlie"]

    def test_running_twice_changes_nothing(
        self, make_prediction: MakePrediction, add_result: AddResult
    ) -> None:
        make_prediction("Alpha", "Bravo")
        add_result("Alpha", "Bravo", 2, 0)
        resolve_predictions(now=NOW)
        before = list(Resolution.objects.values())

        second = resolve_predictions(now=NOW + timedelta(days=1))

        assert second.resolved == []
        assert list(Resolution.objects.values()) == before

    def test_a_later_result_resolves_on_the_next_run(
        self, make_prediction: MakePrediction, add_result: AddResult
    ) -> None:
        make_prediction("Alpha", "Bravo")
        resolve_predictions(now=NOW)
        assert Resolution.objects.count() == 0

        add_result("Alpha", "Bravo", 1, 0)
        resolve_predictions(now=NOW + timedelta(days=1))

        assert Resolution.objects.count() == 1

    def test_a_result_from_another_season_does_not_count(
        self, make_prediction: MakePrediction, teams: dict[str, Team]
    ) -> None:
        make_prediction("Alpha", "Bravo")
        Match.objects.create(
            season="2526",
            date=date(2026, 1, 17),
            home=teams["Alpha"],
            away=teams["Bravo"],
            home_goals=4,
            away_goals=0,
            ftr="H",
        )

        resolve_predictions(now=NOW)

        assert Resolution.objects.count() == 0

    def test_rejects_a_naive_clock(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            resolve_predictions(now=datetime(2026, 10, 19, 5, 45))


class TestResolutionModel:
    def test_one_resolution_per_prediction(self, make_prediction: MakePrediction) -> None:
        prediction = make_prediction("Alpha", "Bravo")
        Resolution.objects.create(
            prediction=prediction, home_goals=1, away_goals=0, outcome="H", resolved_at=NOW
        )

        with pytest.raises(IntegrityError):
            Resolution.objects.create(
                prediction=prediction, home_goals=1, away_goals=0, outcome="H", resolved_at=NOW
            )

    def test_the_outcome_must_match_the_score(self, make_prediction: MakePrediction) -> None:
        prediction = make_prediction("Alpha", "Bravo")

        with pytest.raises(IntegrityError):
            Resolution.objects.create(
                prediction=prediction, home_goals=0, away_goals=2, outcome="H", resolved_at=NOW
            )


class TestResolveCommand:
    def test_prints_what_it_resolved_and_what_is_waiting(
        self, make_prediction: MakePrediction, add_result: AddResult
    ) -> None:
        make_prediction("Alpha", "Bravo")
        make_prediction("Charlie", "Delta")
        add_result("Alpha", "Bravo", 2, 1)
        out = StringIO()

        call_command("resolve_predictions", stdout=out)

        text = out.getvalue()
        assert "resolved 1 fixture" in text
        assert "1 still without a result" in text
        assert "Alpha 2-1 Bravo" in text
