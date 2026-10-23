from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from itertools import count
from typing import Any

import pytest
from rest_framework.test import APIClient

from football.models import Fixture, Match, ModelRun, Team
from track_record.models import FixturePrediction, Resolution
from track_record.serializers import TrackRecordSerializer

pytestmark = pytest.mark.django_db

URL = "/api/v1/track-record"
FROZEN_AT = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 17, 13, 30, tzinfo=UTC)

AddFixture = Callable[..., FixturePrediction]


@pytest.fixture
def add_fixture() -> AddFixture:
    run = ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0018,
        rho=-0.1,
        home_adv=0.25,
        log_likelihood=-1.0,
        n_matches=100,
    )
    team_ids = count(1)

    def team(name: str) -> Team:
        return Team.objects.get_or_create(name=name, defaults={"code": f"T{next(team_ids):02d}"})[0]

    def build(
        home: str,
        away: str,
        *,
        probs: tuple[float, float, float] = (0.5, 0.3, 0.2),
        score: tuple[int, int] | None = None,
        closing_odds: tuple[float, float, float] | None = None,
        matchday: int = 1,
        season: str = "2627",
        frozen_at: datetime = FROZEN_AT,
    ) -> FixturePrediction:
        home_team, away_team = team(home), team(away)
        fixture = Fixture.objects.create(
            season=season,
            matchday=matchday,
            kickoff_utc=KICKOFF,
            home=home_team,
            away=away_team,
        )
        prediction = FixturePrediction.objects.create(
            fixture=fixture,
            model_run=run,
            p_home=probs[0],
            p_draw=probs[1],
            p_away=probs[2],
            exp_home_goals=1.5,
            exp_away_goals=1.1,
            score_grid=[[0.0] * 11 for _ in range(11)],
            created_at=frozen_at,
        )
        if score is not None:
            outcome = "H" if score[0] > score[1] else "A" if score[0] < score[1] else "D"
            Resolution.objects.create(
                prediction=prediction,
                home_goals=score[0],
                away_goals=score[1],
                outcome=outcome,
                resolved_at=KICKOFF + timedelta(days=2),
            )
            odds = closing_odds or (None, None, None)
            Match.objects.create(
                season=season,
                date=date(2026, 10, 17),
                home=home_team,
                away=away_team,
                home_goals=score[0],
                away_goals=score[1],
                ftr=outcome,
                avgc_home=odds[0],
                avgc_draw=odds[1],
                avgc_away=odds[2],
            )
        return prediction

    return build


def fetch(client: APIClient, **params: str) -> Any:
    response = client.get(URL, params)
    assert response.status_code == 200
    return response.json()


class TestEmptyRecord:
    def test_has_no_live_numbers_before_anything_is_resolved(self, api_client: APIClient) -> None:
        body = fetch(api_client)

        live = body["live"]
        assert live["model"] is None
        assert live["bookmaker"] is None
        assert live["base_rate"] is None
        assert live["since"] is None
        assert body["matchdays"] == []
        assert body["calibration"] == []

    def test_still_serves_the_backtest(self, api_client: APIClient) -> None:
        backtest = fetch(api_client)["backtest"]

        assert backtest["kind"] == "backtest"
        assert backtest["label"] == "Backtest, 5 seasons"
        assert backtest["model"]["n_fixtures"] == 1827
        assert backtest["model"]["rps"] == 0.2045
        assert backtest["bookmaker"]["rps"] == 0.1967
        assert backtest["model"]["hit_rate"] is None
        assert [f["key"] for f in backtest["forecasters"]][0] == "market_close"


class TestLiveSummary:
    def test_scores_the_model_against_the_market_and_the_base_rate(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture(
            "Alpha", "Bravo", probs=(0.5, 0.3, 0.2), score=(2, 0), closing_odds=(2.0, 4.0, 4.0)
        )

        live = fetch(api_client)["live"]

        assert live["model"] == {
            "n_fixtures": 1,
            "rps": pytest.approx(0.145),
            "log_loss": pytest.approx(-math.log(0.5)),
            "hit_rate": 1.0,
        }
        # 1/2 + 1/4 + 1/4 = 1.0, so the de-vigged market is (0.5, 0.25, 0.25).
        assert live["bookmaker"]["rps"] == pytest.approx(0.5 * ((0.5 - 1) ** 2 + (0.75 - 1) ** 2))
        assert live["base_rate"]["rps"] == pytest.approx(0.5 * (0.56**2 + 0.31**2))

    def test_label_and_since_come_from_the_first_frozen_prediction(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", score=(1, 1))
        add_fixture("Charlie", "Delta", frozen_at=FROZEN_AT + timedelta(days=3), score=(0, 1))

        live = fetch(api_client)["live"]

        assert live["since"] == "2026-10-15"
        assert live["label"] == "Live since 2026-10-15"

    def test_unresolved_fixtures_are_not_scored(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", score=(2, 0))
        add_fixture("Charlie", "Delta")

        live = fetch(api_client)["live"]

        assert live["model"]["n_fixtures"] == 1

    def test_the_market_is_scored_only_where_closing_odds_exist(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", score=(2, 0), closing_odds=(2.0, 4.0, 4.0))
        add_fixture("Charlie", "Delta", score=(0, 0))

        live = fetch(api_client)["live"]

        assert live["model"]["n_fixtures"] == 2
        assert live["bookmaker"]["n_fixtures"] == 1


class TestMatchdays:
    def test_one_row_per_matchday_newest_first(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", matchday=5, score=(2, 0))
        add_fixture("Charlie", "Delta", matchday=5, probs=(0.2, 0.3, 0.5), score=(0, 1))
        add_fixture("Alpha", "Charlie", matchday=6)

        matchdays = fetch(api_client)["matchdays"]

        assert [m["matchday"] for m in matchdays] == [6, 5]
        assert matchdays[0]["n_fixtures"] == 1
        assert matchdays[0]["n_resolved"] == 0
        assert matchdays[0]["rps"] is None
        assert matchdays[0]["fixtures"] == []
        assert matchdays[1]["n_resolved"] == 2
        assert matchdays[1]["rps"] == pytest.approx((0.145 + 0.5 * (0.5**2 + 0.2**2)) / 2)
        assert matchdays[1]["hit_rate"] == 1.0

    def test_lists_each_resolved_fixture_with_its_frozen_probabilities(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", matchday=1, probs=(0.6, 0.25, 0.15), score=(0, 3))

        row = fetch(api_client)["matchdays"][0]["fixtures"][0]

        assert row["home"] == {"name": "Alpha", "code": "T01"}
        assert row["away"] == {"name": "Bravo", "code": "T02"}
        assert (row["home_goals"], row["away_goals"], row["outcome"]) == (0, 3, "A")
        assert (row["p_home"], row["p_draw"], row["p_away"]) == (0.6, 0.25, 0.15)
        assert row["rps"] == pytest.approx(0.54125)
        assert row["hit"] is False

    def test_matchday_rows_carry_the_market_and_base_rate_rps(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", score=(2, 0), closing_odds=(2.0, 4.0, 4.0))

        row = fetch(api_client)["matchdays"][0]

        assert row["bookmaker_rps"] == pytest.approx(0.5 * (0.5**2 + 0.25**2))
        assert row["base_rate_rps"] == pytest.approx(0.5 * (0.56**2 + 0.31**2))


class TestNewsEdge:
    def test_is_empty_with_no_rate_when_nothing_is_logged(self, api_client: APIClient) -> None:
        edge = fetch(api_client)["news_edge"]

        assert edge["n_logged"] == 0
        assert edge["chats"] == []
        assert edge["rate"] is None
        assert edge["minimum_for_rate"] == 20


class TestSeasonFilter:
    def test_defaults_to_the_newest_season(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", season="2526", score=(1, 0))
        add_fixture("Charlie", "Delta", season="2627", score=(1, 0))

        body = fetch(api_client)

        assert [m["season"] for m in body["matchdays"]] == ["2627"]

    def test_season_parameter_picks_another_one(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", season="2526", score=(1, 0))
        add_fixture("Charlie", "Delta", season="2627", score=(1, 0))

        body = fetch(api_client, season="2526")

        assert body["season"] == "2526"
        assert [m["season"] for m in body["matchdays"]] == ["2526"]


class TestCalibration:
    def test_pools_resolved_predictions_into_bins(
        self, api_client: APIClient, add_fixture: AddFixture
    ) -> None:
        add_fixture("Alpha", "Bravo", probs=(0.5, 0.3, 0.2), score=(2, 0))

        bins = fetch(api_client)["calibration"]

        assert sum(b["count"] for b in bins) == 3
        top = next(b for b in bins if b["lower"] == pytest.approx(0.5))
        assert top["observed_rate"] == 1.0


def test_response_matches_the_declared_contract(
    api_client: APIClient, add_fixture: AddFixture
) -> None:
    add_fixture("Alpha", "Bravo", score=(2, 0), closing_odds=(2.0, 4.0, 4.0))
    add_fixture("Charlie", "Delta", matchday=2)

    serializer = TrackRecordSerializer(data=fetch(api_client))

    assert serializer.is_valid(), serializer.errors
