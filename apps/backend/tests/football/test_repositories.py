from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from football import repositories
from football.models import Fixture, Match, ModelRun, Team, TeamAlias, TeamParam

pytestmark = pytest.mark.django_db


def make_team(name: str, **fields: object) -> Team:
    return Team.objects.create(name=name, **fields)


def make_run(
    trained_at: datetime, as_of_date: date | None = None, version: str | None = None
) -> ModelRun:
    return ModelRun.objects.create(
        trained_at=trained_at,
        model_type="dixon_coles",
        as_of_date=as_of_date,
        version=version,
        xi=0.0018,
        rho=-0.1,
        home_adv=0.25,
        log_likelihood=-1000.0,
        n_matches=5000,
    )


def make_match(home: Team, away: Team, played_on: date, home_goals: int, away_goals: int) -> Match:
    return Match.objects.create(
        # A season per day lets one pairing repeat without hitting uq_match_season_home_away.
        season=played_on.isoformat(),
        date=played_on,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        ftr="H" if home_goals > away_goals else "A" if home_goals < away_goals else "D",
    )


def make_fixture(
    home: Team, away: Team, kickoff: datetime, matchday: int, season: str = "2627"
) -> Fixture:
    return Fixture.objects.create(
        season=season, matchday=matchday, kickoff_utc=kickoff, home=home, away=away
    )


class TestLatestModelRun:
    def test_none_before_any_run_exists(self) -> None:
        assert repositories.latest_model_run() is None

    def test_returns_the_most_recently_trained_run(self) -> None:
        make_run(datetime(2026, 9, 1, tzinfo=UTC))
        newest = make_run(datetime(2026, 10, 1, tzinfo=UTC))
        make_run(datetime(2026, 8, 1, tzinfo=UTC))

        assert repositories.latest_model_run() == newest

    def test_breaks_a_trained_at_tie_with_the_higher_id(self) -> None:
        moment = datetime(2026, 10, 1, tzinfo=UTC)
        make_run(moment)
        second = make_run(moment)

        assert repositories.latest_model_run() == second

    def test_can_be_pinned_to_the_run_written_for_a_cutoff(self) -> None:
        cutoff_run = make_run(datetime(2026, 9, 1, tzinfo=UTC), as_of_date=date(2026, 8, 28))
        make_run(datetime(2026, 10, 1, tzinfo=UTC), as_of_date=date(2026, 9, 25))

        assert repositories.latest_model_run(as_of_date=date(2026, 8, 28)) == cutoff_run
        assert repositories.latest_model_run(as_of_date=date(2026, 1, 1)) is None

    def test_can_be_limited_to_one_version(self) -> None:
        serving = make_run(datetime(2026, 9, 1, tzinfo=UTC), version="serve")
        make_run(datetime(2026, 10, 1, tzinfo=UTC), version="walk-forward")
        make_run(datetime(2026, 10, 2, tzinfo=UTC))

        assert repositories.latest_model_run(version="serve") == serving
        assert repositories.latest_model_run(version="missing") is None

    def test_version_and_cutoff_combine(self) -> None:
        make_run(datetime(2026, 9, 1, tzinfo=UTC), as_of_date=date(2026, 8, 28), version="serve")
        wanted = make_run(
            datetime(2026, 9, 2, tzinfo=UTC), as_of_date=date(2026, 8, 28), version="walk-forward"
        )

        run = repositories.latest_model_run(as_of_date=date(2026, 8, 28), version="walk-forward")

        assert run == wanted


class TestRatingsFor:
    def test_rebuilds_the_run_as_engine_ratings_sorted_by_team_name(self) -> None:
        bayern, augsburg = make_team("Bayern Munich"), make_team("FC Augsburg")
        run = make_run(datetime(2026, 10, 1, tzinfo=UTC))
        TeamParam.objects.create(model_run=run, team=bayern, attack=0.4, defense=-0.3)
        TeamParam.objects.create(model_run=run, team=augsburg, attack=0.1, defense=0.2)

        ratings = repositories.ratings_for(run)

        assert ratings.teams == ("Bayern Munich", "FC Augsburg")
        assert list(ratings.attack) == [0.4, 0.1]
        assert list(ratings.defense) == [-0.3, 0.2]
        assert (ratings.home_adv, ratings.rho) == (run.home_adv, run.rho)


class TestTeamParamsFor:
    def test_returns_only_that_runs_params_ordered_by_team_name(self) -> None:
        bayern, augsburg = make_team("Bayern Munich"), make_team("FC Augsburg")
        run, other_run = (
            make_run(datetime(2026, 10, 1, tzinfo=UTC)),
            make_run(datetime(2026, 10, 2, tzinfo=UTC)),
        )
        TeamParam.objects.create(model_run=run, team=bayern, attack=0.4, defense=-0.3)
        TeamParam.objects.create(model_run=run, team=augsburg, attack=0.0, defense=0.1)
        TeamParam.objects.create(model_run=other_run, team=bayern, attack=9.0, defense=9.0)

        params = repositories.team_params_for(run)

        assert [(p.team.name, p.attack) for p in params] == [
            ("Bayern Munich", 0.4),
            ("FC Augsburg", 0.0),
        ]

    def test_loads_teams_without_an_extra_query_per_row(
        self, django_assert_num_queries: DjangoAssertNumQueries
    ) -> None:
        run = make_run(datetime(2026, 10, 1, tzinfo=UTC))
        for index in range(3):
            TeamParam.objects.create(
                model_run=run, team=make_team(f"Club {index}"), attack=0.0, defense=0.0
            )

        with django_assert_num_queries(1):
            names = [param.team.name for param in repositories.team_params_for(run)]

        assert names == ["Club 0", "Club 1", "Club 2"]


class TestResolveTeam:
    def test_canonical_name(self) -> None:
        bayern = make_team("Bayern Munich")

        assert repositories.resolve_team("Bayern Munich") == bayern

    def test_source_alias(self) -> None:
        koeln = make_team("1.FC Köln")
        TeamAlias.objects.create(alias="FC Koln", source="football-data", team=koeln)

        assert repositories.resolve_team("FC Koln") == koeln

    def test_ignores_case_and_surrounding_whitespace(self) -> None:
        dortmund = make_team("Borussia Dortmund")
        TeamAlias.objects.create(alias="Dortmund", source="football-data", team=dortmund)

        assert repositories.resolve_team("  borussia dortmund ") == dortmund
        assert repositories.resolve_team("DORTMUND") == dortmund

    def test_exact_canonical_name_wins_over_a_case_insensitive_alias(self) -> None:
        exact = make_team("Hertha")
        other = make_team("Hertha BSC")
        TeamAlias.objects.create(alias="hertha", source="football-data", team=other)

        assert repositories.resolve_team("Hertha") == exact

    def test_unknown_name_is_none(self) -> None:
        make_team("Bayern Munich")

        assert repositories.resolve_team("Real Madrid") is None


class TestTeamForm:
    def setup_method(self) -> None:
        self.team = Team.objects.create(name="Bayern Munich")
        self.rival = Team.objects.create(name="Borussia Dortmund")

    def test_summarises_results_from_the_teams_perspective_newest_first(self) -> None:
        make_match(self.team, self.rival, date(2026, 9, 1), 3, 0)
        make_match(self.rival, self.team, date(2026, 9, 8), 2, 2)
        make_match(self.team, self.rival, date(2026, 9, 15), 0, 1)

        form = repositories.team_form(self.team, date(2026, 10, 1))

        assert [(m.date, m.venue, m.result) for m in form.matches] == [
            (date(2026, 9, 15), "H", "L"),
            (date(2026, 9, 8), "A", "D"),
            (date(2026, 9, 1), "H", "W"),
        ]
        assert (form.played, form.wins, form.draws, form.losses) == (3, 1, 1, 1)
        assert (form.points, form.goals_for, form.goals_against) == (4, 5, 3)
        assert form.matches[0].opponent == "Borussia Dortmund"

    def test_as_of_excludes_the_match_day_itself_and_everything_later(self) -> None:
        make_match(self.team, self.rival, date(2026, 9, 1), 1, 0)
        make_match(self.team, self.rival, date(2026, 9, 8), 5, 0)
        make_match(self.team, self.rival, date(2026, 9, 9), 7, 0)

        form = repositories.team_form(self.team, date(2026, 9, 8))

        assert [m.date for m in form.matches] == [date(2026, 9, 1)]
        assert form.goals_for == 1

    def test_limits_to_the_last_n_matches(self) -> None:
        for day in range(1, 8):
            make_match(self.team, self.rival, date(2026, 9, day), day, 0)

        form = repositories.team_form(self.team, date(2026, 10, 1), n=3)

        assert [m.date.day for m in form.matches] == [7, 6, 5]
        assert form.played == 3

    def test_a_team_without_earlier_matches_has_empty_form(self) -> None:
        form = repositories.team_form(self.team, date(2026, 8, 1))

        assert form.played == 0
        assert form.matches == ()
        assert form.points == 0


class TestUpcomingFixtures:
    def setup_method(self) -> None:
        names = ["Bayern Munich", "Borussia Dortmund", "RB Leipzig", "FC Augsburg"]
        self.bayern, self.dortmund, self.leipzig, self.augsburg = (
            Team.objects.create(name=n) for n in names
        )
        self.friday = datetime(2026, 8, 28, 18, 30, tzinfo=UTC)

    def test_next_matchday_includes_games_already_kicked_off_that_matchday(self) -> None:
        opener = make_fixture(self.bayern, self.leipzig, self.friday, 1)
        later = make_fixture(self.dortmund, self.augsburg, self.friday + timedelta(days=1), 1)
        make_fixture(self.augsburg, self.bayern, self.friday + timedelta(days=8), 2)

        fixtures = repositories.upcoming_fixtures("next_matchday", self.friday + timedelta(hours=3))

        assert fixtures == [opener, later]

    def test_next_matchday_moves_on_once_the_whole_matchday_has_kicked_off(self) -> None:
        make_fixture(self.bayern, self.leipzig, self.friday, 1)
        second = make_fixture(self.augsburg, self.bayern, self.friday + timedelta(days=8), 2)

        fixtures = repositories.upcoming_fixtures("next_matchday", self.friday + timedelta(days=3))

        assert fixtures == [second]

    def test_next_matchday_follows_the_season_boundary(self) -> None:
        make_fixture(
            self.bayern, self.leipzig, self.friday - timedelta(days=300), 34, season="2526"
        )
        opener = make_fixture(self.bayern, self.leipzig, self.friday, 1)

        assert repositories.upcoming_fixtures(
            "next_matchday", self.friday - timedelta(days=30)
        ) == [opener]

    def test_week_is_a_half_open_seven_day_window_from_as_of(self) -> None:
        as_of = datetime(2026, 9, 1, 12, tzinfo=UTC)
        make_fixture(self.bayern, self.leipzig, as_of - timedelta(minutes=1), 1)
        starts_now = make_fixture(self.bayern, self.dortmund, as_of, 2)
        inside = make_fixture(self.leipzig, self.augsburg, as_of + timedelta(days=6, hours=23), 2)
        make_fixture(self.augsburg, self.bayern, as_of + timedelta(days=7), 3)

        assert repositories.upcoming_fixtures("week", as_of) == [starts_now, inside]

    def test_orders_by_kickoff_then_id_and_loads_teams_without_a_query_per_fixture(
        self, django_assert_num_queries: DjangoAssertNumQueries
    ) -> None:
        later = make_fixture(self.bayern, self.leipzig, self.friday + timedelta(hours=2), 1)
        first = make_fixture(self.dortmund, self.augsburg, self.friday, 1)

        with django_assert_num_queries(2):
            fixtures = repositories.upcoming_fixtures(
                "next_matchday", self.friday - timedelta(days=1)
            )
            names = [f.home.name for f in fixtures]

        assert fixtures == [first, later]
        assert names == ["Borussia Dortmund", "Bayern Munich"]

    def test_nothing_scheduled_gives_an_empty_list(self) -> None:
        assert repositories.upcoming_fixtures("next_matchday", self.friday) == []
        assert repositories.upcoming_fixtures("week", self.friday) == []

    def test_a_naive_as_of_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            repositories.upcoming_fixtures("week", datetime(2026, 9, 1, 12))
