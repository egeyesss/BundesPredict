from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from football.models import Fixture, ModelRun, Team, TeamParam

pytestmark = pytest.mark.django_db

CLUBS = {
    "Bayern Munich": ("FCB", "Bayern", 0.6, -0.3),
    "Borussia Dortmund": ("BVB", "Dortmund", 0.4, -0.1),
    "RB Leipzig": ("RBL", "Leipzig", 0.3, -0.1),
    "Hamburger SV": ("HSV", "Hamburg", -0.3, 0.2),
}


def _seed_run() -> ModelRun:
    run = ModelRun.objects.create(
        model_type="dixon_coles", xi=0.002, rho=-0.1, home_adv=0.3, log_likelihood=-1.0, n_matches=9
    )
    for name, (_, _, attack, defense) in CLUBS.items():
        TeamParam.objects.create(
            model_run=run, team=Team.objects.get(name=name), attack=attack, defense=defense
        )
    return run


@pytest.fixture
def teams() -> dict[str, Team]:
    created = {
        name: Team.objects.create(name=name, code=code, short_name=short)
        for name, (code, short, _, _) in CLUBS.items()
    }
    created["Old Club"] = Team.objects.create(name="Old Club")
    return created


def _fixture(teams: dict[str, Team], home: str, away: str, days: float, matchday: int) -> Fixture:
    return Fixture.objects.create(
        season="2026-27",
        matchday=matchday,
        kickoff_utc=timezone.now() + timedelta(days=days),
        home=teams[home],
        away=teams[away],
    )


def test_teams_lists_clubs_with_codes_and_crests(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    response = api_client.get("/api/v1/teams")

    assert response.status_code == 200
    body = response.json()
    assert [t["name"] for t in body] == sorted(CLUBS)
    assert body[0] == {
        "id": teams["Bayern Munich"].id,
        "name": "Bayern Munich",
        "short_name": "Bayern",
        "code": "FCB",
        "crest": "/crests/FCB.svg",
    }


def test_teams_leaves_out_clubs_without_a_code(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    names = [t["name"] for t in api_client.get("/api/v1/teams").json()]

    assert "Old Club" not in names


def test_fixture_list_defaults_to_the_next_matchday(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    run = _seed_run()
    _fixture(teams, "Bayern Munich", "Hamburger SV", days=2, matchday=5)
    _fixture(teams, "Borussia Dortmund", "RB Leipzig", days=3, matchday=5)
    _fixture(teams, "RB Leipzig", "Bayern Munich", days=10, matchday=6)

    response = api_client.get("/api/v1/fixtures")

    assert response.status_code == 200
    cards = response.json()
    assert [c["matchday"] for c in cards] == [5, 5]
    first = cards[0]
    assert first["home"]["code"] == "FCB" and first["away"]["crest"] == "/crests/HSV.svg"
    assert first["season"] == "2026-27"
    assert first["model_run_id"] == run.id
    base = first["base"]
    assert base["p_home"] + base["p_draw"] + base["p_away"] == pytest.approx(1.0, abs=1e-3)
    assert base["p_home"] > base["p_away"]
    assert base["exp_home_goals"] > base["exp_away_goals"]


def test_fixture_list_week_scope_stops_at_seven_days(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _seed_run()
    _fixture(teams, "Bayern Munich", "Hamburger SV", days=2, matchday=5)
    _fixture(teams, "RB Leipzig", "Bayern Munich", days=10, matchday=6)

    cards = api_client.get("/api/v1/fixtures", {"scope": "week"}).json()

    assert [c["matchday"] for c in cards] == [5]


def test_fixture_list_is_empty_when_nothing_is_scheduled(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _seed_run()

    assert api_client.get("/api/v1/fixtures").json() == []


def test_fixture_list_skips_fixtures_the_run_has_no_ratings_for(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _seed_run()
    newcomer = Team.objects.create(name="SV 07 Elversberg", code="SVE", short_name="Elversberg")
    teams[newcomer.name] = newcomer
    _fixture(teams, "Bayern Munich", "Hamburger SV", days=2, matchday=5)
    _fixture(teams, "SV 07 Elversberg", "RB Leipzig", days=2, matchday=5)

    cards = api_client.get("/api/v1/fixtures").json()

    assert [c["home"]["code"] for c in cards] == ["FCB"]


def test_fixture_list_rejects_an_unknown_scope(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/fixtures", {"scope": "season"})

    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"


def test_fixture_list_answers_503_without_a_model_run(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _fixture(teams, "Bayern Munich", "Hamburger SV", days=2, matchday=5)

    response = api_client.get("/api/v1/fixtures")

    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"


def test_fixture_detail_adds_the_full_markets(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _seed_run()
    fixture = _fixture(teams, "Borussia Dortmund", "RB Leipzig", days=3, matchday=5)

    response = api_client.get(f"/api/v1/fixtures/{fixture.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == fixture.id
    markets = body["markets"]
    assert len(markets["score_grid"]) == 11 and all(len(row) == 11 for row in markets["score_grid"])
    assert sum(sum(row) for row in markets["score_grid"]) == pytest.approx(1.0, abs=1e-4)
    assert markets["p_home"] == body["base"]["p_home"]
    assert len(markets["top_scores"]) == 5


def test_fixture_detail_404_for_an_unknown_id(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _seed_run()

    response = api_client.get("/api/v1/fixtures/999")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_fixture_detail_answers_503_when_the_run_has_no_ratings_for_a_team(
    api_client: APIClient, teams: dict[str, Team]
) -> None:
    _seed_run()
    newcomer = Team.objects.create(name="SV 07 Elversberg", code="SVE", short_name="Elversberg")
    teams[newcomer.name] = newcomer
    fixture = _fixture(teams, "SV 07 Elversberg", "RB Leipzig", days=2, matchday=5)

    response = api_client.get(f"/api/v1/fixtures/{fixture.id}")

    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"
