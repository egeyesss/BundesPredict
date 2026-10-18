"""The Django ports hand the agent the recorded grounding facts, tool by tool."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from bundespredict.agent.ports import AgentDataPorts
from bundespredict.agent.service import PredictionService
from bundespredict.agent.tools import dispatch
from bundespredict.model.dixon_coles import TeamRatings
from football.models import Fixture, Match, ModelRun, Player, Team, TeamParam
from predictions.ports import DjangoAgentPorts

pytestmark = pytest.mark.django_db(transaction=True)

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
TODAY = date(2026, 10, 16)

RECORDED = json.loads((Path(__file__).parent / "recorded" / "agent_port_outcomes.json").read_text())
# An undated service reads the schedule from the real today, so only the dated run can use the
# recording for fixtures.
CASES = [(recorded, TODAY) for recorded in RECORDED] + [
    (recorded, None) for recorded in RECORDED if recorded["tool"] != "get_upcoming_fixtures"
]


@pytest.fixture
def seeded() -> None:
    dortmund, leipzig = Team.objects.create(name=HOME), Team.objects.create(name=AWAY)
    for number, (home, away, goals) in enumerate(
        ((dortmund, leipzig, (2, 0)), (leipzig, dortmund, (1, 1)), (dortmund, leipzig, (0, 3)))
    ):
        Match.objects.create(
            season=f"25{number}",
            date=TODAY - timedelta(days=30 - number),
            home=home,
            away=away,
            home_goals=goals[0],
            away_goals=goals[1],
            ftr="H" if goals[0] > goals[1] else "A" if goals[0] < goals[1] else "D",
        )
    midday = datetime.combine(TODAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=13)
    Fixture.objects.create(
        season="2627",
        matchday=1,
        kickoff_utc=midday + timedelta(days=3),
        home=dortmund,
        away=leipzig,
    )
    Fixture.objects.create(
        season="2627",
        matchday=2,
        kickoff_utc=midday + timedelta(days=10),
        home=leipzig,
        away=dortmund,
    )
    scraped = datetime(2026, 10, 1, tzinfo=UTC)
    for tm_id, team, name, value in (
        (1, dortmund, "Serhou Guirassy", 60_000_000),
        (2, dortmund, "Reserve Keeper", 1_000_000),
        (3, leipzig, "Benjamin Sesko", 70_000_000),
    ):
        Player.objects.create(
            tm_id=tm_id,
            team=team,
            name=name,
            position="Forward",
            market_value_eur=value,
            scraped_at=scraped,
        )


def _service(ports: AgentDataPorts, as_of: date | None) -> PredictionService:
    ratings = TeamRatings(
        teams=(HOME, AWAY),
        attack=np.array([0.4, -0.4]),
        defense=np.array([-0.2, 0.2]),
        home_adv=0.3,
        rho=-0.12,
        log_likelihood=0.0,
    )
    return PredictionService(ratings, ports=ports, as_of_date=as_of)


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize(
    ("recorded", "as_of"),
    CASES,
    ids=[f"{r['tool']}-{r['input']}-{'dated' if a else 'undated'}" for r, a in CASES],
)
def test_tool_outcome_matches_the_recording(recorded: dict[str, Any], as_of: date | None) -> None:
    outcome = dispatch(recorded["tool"], recorded["input"], _service(DjangoAgentPorts(), as_of))

    assert outcome.payload == recorded["payload"]
    assert outcome.is_error == recorded["is_error"]


@pytest.mark.usefixtures("seeded")
def test_grounding_context_reports_the_latest_stored_result() -> None:
    context = _service(DjangoAgentPorts(), TODAY).context

    assert context.today == TODAY
    assert context.data_through == date(2026, 9, 18)


@pytest.mark.usefixtures("seeded")
def test_the_seed_gives_the_recording_something_to_say() -> None:
    """Guards the recording against being re-made from an empty seed."""
    service = _service(DjangoAgentPorts(), TODAY)

    form = dispatch("get_team_form", {"team": HOME}, service).payload
    upcoming = dispatch("get_upcoming_fixtures", {}, service).payload
    player = dispatch("lookup_player", {"name": "guirassy"}, service).payload

    assert form["played"] == 3
    assert [f["matchday"] for f in upcoming["fixtures"]] == [1, 2]
    assert all(f["kickoff_utc"].endswith("00Z") for f in upcoming["fixtures"])
    assert "+" not in upcoming["fixtures"][0]["kickoff_utc"]
    assert player["found"] is True and player["importance"] == "medium"


def test_latest_ratings_are_none_before_a_serving_fit_exists() -> None:
    ModelRun.objects.create(
        model_type="dixon_coles",
        version="walk-forward",
        xi=0.0,
        rho=0.0,
        home_adv=0.0,
        log_likelihood=0.0,
        n_matches=1,
    )

    assert DjangoAgentPorts().latest_ratings() is None


def test_latest_ratings_come_from_the_newest_serving_fit() -> None:
    dortmund = Team.objects.create(name=HOME)
    old, new = (
        ModelRun.objects.create(
            model_type="dixon_coles",
            version="serve",
            trained_at=datetime(2026, 10, day, tzinfo=UTC),
            xi=0.0,
            rho=-0.1,
            home_adv=0.25,
            log_likelihood=0.0,
            n_matches=day,
        )
        for day in (1, 2)
    )
    ModelRun.objects.create(
        model_type="dixon_coles",
        version="walk-forward",
        trained_at=datetime(2026, 10, 3, tzinfo=UTC),
        xi=0.0,
        rho=0.0,
        home_adv=0.0,
        log_likelihood=0.0,
        n_matches=3,
    )
    TeamParam.objects.create(model_run=old, team=dortmund, attack=1.0, defense=1.0)
    TeamParam.objects.create(model_run=new, team=dortmund, attack=0.5, defense=-0.5)

    serving = DjangoAgentPorts().latest_ratings()

    assert serving is not None
    assert serving.run_id == new.id
    assert serving.ratings.teams == (HOME,)
    assert list(serving.ratings.attack) == [0.5]


def test_saving_a_prediction_for_an_unstored_team_is_a_value_error() -> None:
    ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0,
        rho=0.0,
        home_adv=0.0,
        log_likelihood=0.0,
        n_matches=1,
    )
    service = _service(DjangoAgentPorts(), None)
    service.predict_match(HOME, AWAY)
    assert service.last_prediction is not None

    with pytest.raises(ValueError, match="no teams row for"):
        DjangoAgentPorts().save(
            model_run_id=ModelRun.objects.get().id,
            record=service.last_prediction,
            explanation="x",
            query="q",
            match_date=None,
        )
