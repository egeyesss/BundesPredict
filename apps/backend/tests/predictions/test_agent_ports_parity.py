"""The Django ports hand the agent exactly what the SQLAlchemy ports do, tool by tool."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from django.db import connection
from sqlalchemy import Engine

from bundespredict.agent.ports import AgentDataPorts
from bundespredict.agent.service import PredictionService
from bundespredict.agent.tools import dispatch
from bundespredict.data.agent_ports import SqlAlchemyPorts
from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.model.dixon_coles import TeamRatings
from football.models import Fixture, Match, ModelRun, Player, Team, TeamParam
from predictions.ports import DjangoAgentPorts

pytestmark = pytest.mark.django_db(transaction=True)

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
TODAY = date(2026, 10, 16)

TOOL_CALLS: list[tuple[str, dict[str, Any]]] = [
    ("get_team_form", {"team": HOME}),
    ("get_team_form", {"team": HOME, "n": 1}),
    ("get_team_form", {"team": "Atlantis FC"}),
    ("get_recent_results", {}),
    ("get_recent_results", {"n": 2}),
    ("get_upcoming_fixtures", {}),
    ("get_upcoming_fixtures", {"team": AWAY}),
    ("get_upcoming_fixtures", {"team": "Atlantis FC"}),
    ("lookup_player", {"name": "Serhou Guirassy"}),
    ("lookup_player", {"name": "guirassy"}),
    ("lookup_player", {"name": "Nobody Atall"}),
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


@pytest.fixture
def engine() -> Iterator[Engine]:
    db = connection.settings_dict
    url = (
        f"postgresql+psycopg://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
    )
    engine = make_engine(url)
    yield engine
    engine.dispose()


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
@pytest.mark.parametrize("as_of", [TODAY, None], ids=["dated", "undated"])
@pytest.mark.parametrize(("tool", "tool_input"), TOOL_CALLS)
def test_tool_outcome_is_the_same_through_both_ports(
    engine: Engine, tool: str, tool_input: dict[str, Any], as_of: date | None
) -> None:
    with make_session_factory(engine)() as session:
        expected = dispatch(tool, tool_input, _service(SqlAlchemyPorts(session), as_of))
    actual = dispatch(tool, tool_input, _service(DjangoAgentPorts(), as_of))

    assert actual == expected


@pytest.mark.usefixtures("seeded")
def test_grounding_context_is_the_same_through_both_ports(engine: Engine) -> None:
    with make_session_factory(engine)() as session:
        expected = _service(SqlAlchemyPorts(session), TODAY).context

    assert _service(DjangoAgentPorts(), TODAY).context == expected
    assert expected.data_through is not None


@pytest.mark.usefixtures("seeded")
def test_the_seed_gives_the_comparisons_something_to_compare(engine: Engine) -> None:
    """A parity test over two empty payloads would pass without proving anything."""
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
