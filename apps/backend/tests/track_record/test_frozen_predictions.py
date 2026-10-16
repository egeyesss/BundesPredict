from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO
from itertools import count

import numpy as np
import pytest
from django.contrib import admin
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from bundespredict.model.dixon_coles import TeamRatings
from football.models import Fixture, ModelRun, Team, TeamParam
from track_record.models import FixturePrediction
from track_record.snapshots import (
    KickoffPassedError,
    NoModelRunError,
    freeze_fixture,
    snapshot_upcoming,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
MakeFixture = Callable[..., Fixture]

# (attack, defense) per team, distinct enough that every fixture gets its own distribution.
STRENGTHS = {
    "Alpha": (0.30, -0.20),
    "Bravo": (0.10, -0.05),
    "Charlie": (-0.10, 0.05),
    "Delta": (-0.30, 0.20),
}
HOME_ADV = 0.25
RHO = -0.1


@dataclass(frozen=True)
class FittedLeague:
    run: ModelRun
    teams: dict[str, Team]

    def new_run(self, trained_at: datetime) -> ModelRun:
        """A later run with the same team parameters."""
        run = create_run(trained_at)
        add_params(run, self.teams)
        return run

    def ratings(self) -> TeamRatings:
        """The engine's view of `run`, built from the same numbers the run was stored with."""
        names = tuple(sorted(STRENGTHS))
        return TeamRatings(
            teams=names,
            attack=np.array([STRENGTHS[name][0] for name in names]),
            defense=np.array([STRENGTHS[name][1] for name in names]),
            home_adv=self.run.home_adv,
            rho=self.run.rho,
            log_likelihood=self.run.log_likelihood,
            xg_coef=self.run.xg_coef,
        )


def create_run(trained_at: datetime | None = None) -> ModelRun:
    fields: dict[str, object] = {
        "model_type": "dixon_coles",
        "xi": 0.0018,
        "rho": RHO,
        "home_adv": HOME_ADV,
        "log_likelihood": -1000.0,
        "n_matches": 5000,
    }
    if trained_at is not None:
        fields["trained_at"] = trained_at
    return ModelRun.objects.create(**fields)


def add_params(run: ModelRun, teams: dict[str, Team]) -> None:
    for name, team in teams.items():
        attack, defense = STRENGTHS[name]
        TeamParam.objects.create(model_run=run, team=team, attack=attack, defense=defense)


@pytest.fixture
def league(db: None) -> FittedLeague:
    teams = {name: Team.objects.create(name=name) for name in STRENGTHS}
    # Pinned to the test clock: the real clock made this run newer than `new_run(NOW + 1 day)`
    # once that moment passed.
    run = create_run(NOW - timedelta(days=1))
    add_params(run, teams)
    return FittedLeague(run=run, teams=teams)


@pytest.fixture
def make_fixture(league: FittedLeague) -> Callable[..., Fixture]:
    matchdays = count(1)

    def build(home: str, away: str, kickoff: datetime) -> Fixture:
        return Fixture.objects.create(
            season="2627",
            matchday=next(matchdays),
            kickoff_utc=kickoff,
            home=league.teams[home],
            away=league.teams[away],
        )

    return build


class TestFreezeFixture:
    def test_stores_what_the_engine_predicts_for_that_run(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW + timedelta(hours=20))
        expected = league.ratings().predict("Alpha", "Delta")

        snapshot = freeze_fixture(fixture, run=league.run, ratings=league.ratings(), now=NOW)
        snapshot.refresh_from_db()

        assert snapshot.p_home == pytest.approx(expected.p_home, rel=1e-12)
        assert snapshot.p_draw == pytest.approx(expected.p_draw, rel=1e-12)
        assert snapshot.p_away == pytest.approx(expected.p_away, rel=1e-12)
        assert snapshot.exp_home_goals == pytest.approx(expected.exp_home_goals, rel=1e-12)
        assert snapshot.exp_away_goals == pytest.approx(expected.exp_away_goals, rel=1e-12)
        assert snapshot.score_grid == [list(row) for row in expected.score_grid]

    def test_score_grid_is_home_goals_rows_by_away_goals_columns(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW + timedelta(hours=20))

        snapshot = freeze_fixture(fixture, run=league.run, ratings=league.ratings(), now=NOW)
        snapshot.refresh_from_db()

        grid = snapshot.score_grid
        assert len(grid) == 11
        assert all(len(row) == 11 for row in grid)
        home_win_mass = sum(grid[i][j] for i in range(11) for j in range(11) if i > j)
        assert home_win_mass == pytest.approx(snapshot.p_home)

    def test_records_the_run_and_the_time_it_was_frozen(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW + timedelta(hours=20))

        snapshot = freeze_fixture(fixture, run=league.run, ratings=league.ratings(), now=NOW)
        snapshot.refresh_from_db()

        assert snapshot.model_run_id == league.run.id
        assert snapshot.created_at == NOW
        assert snapshot.created_at < fixture.kickoff_utc

    def test_refuses_a_fixture_that_kicked_off_already(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW - timedelta(minutes=1))

        with pytest.raises(KickoffPassedError):
            freeze_fixture(fixture, run=league.run, ratings=league.ratings(), now=NOW)

        assert FixturePrediction.objects.count() == 0

    def test_refuses_a_fixture_kicking_off_exactly_now(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW)

        with pytest.raises(KickoffPassedError):
            freeze_fixture(fixture, run=league.run, ratings=league.ratings(), now=NOW)

    def test_accepts_a_fixture_kicking_off_a_microsecond_from_now(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW + timedelta(microseconds=1))

        snapshot = freeze_fixture(fixture, run=league.run, ratings=league.ratings(), now=NOW)

        assert snapshot.pk is not None

    def test_rejects_a_naive_clock(self, league: FittedLeague, make_fixture: MakeFixture) -> None:
        fixture = make_fixture("Alpha", "Delta", NOW + timedelta(hours=20))

        with pytest.raises(ValueError, match="timezone-aware"):
            freeze_fixture(
                fixture, run=league.run, ratings=league.ratings(), now=datetime(2026, 10, 15, 12)
            )


class TestSnapshotUpcoming:
    def test_freezes_every_fixture_in_the_next_48_hours(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        soon = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=1))
        later = make_fixture("Charlie", "Delta", NOW + timedelta(hours=47))

        report = snapshot_upcoming(now=NOW)

        assert {s.fixture_id for s in report.created} == {soon.id, later.id}
        assert report.skipped_without_ratings == []

    def test_leaves_out_fixtures_past_the_window_and_already_played_ones(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        make_fixture("Alpha", "Bravo", NOW - timedelta(hours=2))
        make_fixture("Charlie", "Delta", NOW)
        make_fixture("Alpha", "Charlie", NOW + timedelta(hours=48, seconds=1))
        edge = make_fixture("Bravo", "Delta", NOW + timedelta(hours=48))

        report = snapshot_upcoming(now=NOW)

        assert [s.fixture_id for s in report.created] == [edge.id]

    def test_a_second_run_writes_nothing(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        make_fixture("Alpha", "Bravo", NOW + timedelta(hours=1))
        make_fixture("Charlie", "Delta", NOW + timedelta(hours=30))
        first = snapshot_upcoming(now=NOW)
        stored = list(FixturePrediction.objects.order_by("id").values())

        second = snapshot_upcoming(now=NOW + timedelta(hours=3))

        assert len(first.created) == 2
        assert second.created == []
        assert list(FixturePrediction.objects.order_by("id").values()) == stored

    def test_a_newer_model_run_does_not_rewrite_a_frozen_snapshot(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        fixture = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=1))
        snapshot_upcoming(now=NOW)
        league.new_run(NOW + timedelta(minutes=5))

        report = snapshot_upcoming(now=NOW + timedelta(hours=1))

        assert report.created == []
        assert FixturePrediction.objects.get(fixture=fixture).model_run_id == league.run.id

    def test_uses_the_newest_model_run(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        newer = league.new_run(NOW + timedelta(days=1))
        make_fixture("Alpha", "Bravo", NOW + timedelta(days=2))

        report = snapshot_upcoming(now=NOW + timedelta(days=1, hours=1))

        assert [s.model_run_id for s in report.created] == [newer.id]

    def test_reports_a_team_the_run_has_no_ratings_for_and_freezes_the_rest(
        self, league: FittedLeague, make_fixture: MakeFixture
    ) -> None:
        promoted = Team.objects.create(name="Echo")
        league.teams["Echo"] = promoted
        newcomer = Fixture.objects.create(
            season="2627",
            matchday=99,
            kickoff_utc=NOW + timedelta(hours=5),
            home=promoted,
            away=league.teams["Alpha"],
        )
        covered = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=6))

        report = snapshot_upcoming(now=NOW)

        assert [s.fixture_id for s in report.created] == [covered.id]
        assert report.skipped_without_ratings == [newcomer]

    def test_raises_when_no_model_run_exists(self, db: None) -> None:

        with pytest.raises(NoModelRunError):
            snapshot_upcoming(now=NOW)


def build(league: FittedLeague, fixture: Fixture, **overrides: object) -> FixturePrediction:
    fields: dict[str, object] = {
        "fixture": fixture,
        "model_run": league.run,
        "p_home": 0.5,
        "p_draw": 0.25,
        "p_away": 0.25,
        "exp_home_goals": 1.6,
        "exp_away_goals": 1.1,
        "score_grid": [[1.0]],
        "created_at": NOW,
    }
    return FixturePrediction(**{**fields, **overrides})


def test_a_fixture_can_only_be_snapshotted_once(
    league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    fixture = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=5))
    build(league, fixture).save()

    with pytest.raises(IntegrityError), transaction.atomic():
        build(league, fixture).save()


@pytest.mark.parametrize(
    "overrides",
    [
        {"p_home": 0.6},
        {"p_draw": -0.05, "p_home": 0.8},
        {"p_away": 1.2, "p_home": -0.2, "p_draw": 0.0},
    ],
)
def test_the_database_rejects_probabilities_that_are_not_a_distribution(
    league: FittedLeague, make_fixture: Callable[..., Fixture], overrides: dict[str, float]
) -> None:
    fixture = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=5))

    with pytest.raises(IntegrityError), transaction.atomic():
        build(league, fixture, **overrides).save()


def test_a_stored_snapshot_cannot_be_saved_again(
    league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    fixture = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=5))
    snapshot = build(league, fixture)
    snapshot.save()
    snapshot.p_home = 0.9

    with pytest.raises(RuntimeError, match="frozen"):
        snapshot.save()

    assert FixturePrediction.objects.get().p_home == 0.5


def test_a_stored_snapshot_cannot_be_deleted(
    league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    fixture = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=5))
    snapshot = build(league, fixture)
    snapshot.save()

    with pytest.raises(RuntimeError, match="frozen"):
        snapshot.delete()

    assert FixturePrediction.objects.count() == 1


def test_the_table_name_is_the_django_default() -> None:
    assert FixturePrediction._meta.db_table == "track_record_fixtureprediction"


def run_command() -> str:
    out = StringIO()
    call_command("snapshot_predictions", stdout=out)
    return out.getvalue()


def test_freezes_upcoming_fixtures_and_lists_them(
    league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    fixture = make_fixture("Alpha", "Bravo", timezone.now() + timedelta(hours=10))

    output = run_command()

    snapshot = FixturePrediction.objects.get(fixture=fixture)
    assert snapshot.model_run_id == league.run.id
    assert snapshot.created_at < fixture.kickoff_utc
    assert "froze 1 fixture" in output
    assert "Alpha v Bravo" in output


def test_running_twice_reports_nothing_new(
    league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    make_fixture("Alpha", "Bravo", timezone.now() + timedelta(hours=10))
    run_command()

    output = run_command()

    assert "froze 0 fixtures" in output
    assert FixturePrediction.objects.count() == 1


def test_fails_after_freezing_the_rest_when_a_team_has_no_ratings(
    league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    promoted = Team.objects.create(name="Echo")
    Fixture.objects.create(
        season="2627",
        matchday=50,
        kickoff_utc=timezone.now() + timedelta(hours=5),
        home=promoted,
        away=league.teams["Alpha"],
    )
    make_fixture("Alpha", "Bravo", timezone.now() + timedelta(hours=6))

    with pytest.raises(CommandError, match="Echo v Alpha"):
        run_command()

    assert FixturePrediction.objects.count() == 1


def test_fails_when_no_model_run_exists(db: None) -> None:
    with pytest.raises(CommandError, match="model run"):
        run_command()


def test_snapshots_are_listed_but_cannot_be_added_changed_or_deleted(
    admin_client: Client, league: FittedLeague, make_fixture: Callable[..., Fixture]
) -> None:
    fixture = make_fixture("Alpha", "Bravo", NOW + timedelta(hours=5))
    snapshot = FixturePrediction.objects.create(
        fixture=fixture,
        model_run=league.run,
        p_home=0.5,
        p_draw=0.25,
        p_away=0.25,
        exp_home_goals=1.6,
        exp_away_goals=1.1,
        score_grid=[[1.0]],
        created_at=NOW,
    )
    changelist = reverse("admin:track_record_fixtureprediction_changelist")
    model_admin = admin.site._registry[FixturePrediction]
    request = admin_client.get(changelist).wsgi_request

    assert admin_client.get(changelist).status_code == 200
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
    delete_url = reverse("admin:track_record_fixtureprediction_delete", args=[snapshot.pk])
    assert admin_client.post(delete_url, {"post": "yes"}).status_code == 403
