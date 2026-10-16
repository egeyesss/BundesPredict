"""Every recorded transcript gives the same stages and result through FastAPI and Django.

Both apps read one Postgres (the Django test database), run the same scripted LLM transcript and
persist their audit row, so a difference in the streamed frames or the stored row is a real
behaviour change between the two stacks.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from fastapi.testclient import TestClient
from rest_framework.test import APIClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from tests.agent.fakes import (
    FakeResponse,
    FakeTextBlock,
    FakeToolUseBlock,
    ScriptedClient,
    transcript_full,
    transcript_refusal,
)

from app.config import get_settings
from app.deps import get_llm_client, get_session
from app.main import app as fastapi_app
from app.security import limiter
from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.models import Prediction as SqlPrediction
from football.models import Fixture, Match, ModelRun, Player, Team, TeamParam
from predictions.models import Prediction
from predictions.throttles import throttle_cache

pytestmark = pytest.mark.django_db(transaction=True)

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
THIRD = "Hamburger SV"
QUERY = "striker out, windy"


def _tool(call_id: str, tool: str, **tool_input: Any) -> FakeResponse:
    return FakeResponse(
        content=[FakeToolUseBlock(id=call_id, name=tool, input=tool_input)],
        stop_reason="tool_use",
    )


def _say(text: str) -> FakeResponse:
    return FakeResponse(content=[FakeTextBlock(text)], stop_reason="end_turn")


def transcript_grounding() -> list[FakeResponse]:
    """Every database-backed tool once, then a baseline and an explanation."""
    return [
        _tool("t1", "get_team_form", team=HOME, n=3),
        _tool("t2", "get_recent_results", n=2),
        _tool("t3", "get_upcoming_fixtures", team=HOME),
        _tool("t4", "lookup_player", name="Guirassy"),
        _tool("t5", "predict_match", home=HOME, away=AWAY),
        _say("Dortmund are in decent form and the model has them slight favourites."),
    ]


def transcript_recovers_from_a_bad_team() -> list[FakeResponse]:
    return [
        _tool("t1", "predict_match", home="Atlantis FC", away=AWAY),
        _tool("t2", "get_team_form", team="Atlantis FC"),
        _tool("t3", "predict_match", home=HOME, away=AWAY),
        _say("I could not find Atlantis, so here is Dortmund v Leipzig instead."),
    ]


def transcript_clarification() -> list[FakeResponse]:
    return [_say("Which fixture do you mean?")]


TRANSCRIPTS: dict[str, Callable[[], list[FakeResponse]]] = {
    "full": lambda: transcript_full(HOME, AWAY),
    "refusal": lambda: transcript_refusal(HOME, AWAY),
    "clarification": transcript_clarification,
    "grounding": transcript_grounding,
    "bad_team": transcript_recovers_from_a_bad_team,
}


@pytest.fixture(autouse=True)
def _empty_throttle() -> Iterator[None]:
    throttle_cache.clear()
    yield
    throttle_cache.clear()


@pytest.fixture
def seeded() -> None:
    teams = {name: Team.objects.create(name=name) for name in (HOME, AWAY, THIRD)}
    run = ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0018,
        rho=-0.12,
        home_adv=0.3,
        log_likelihood=-1.0,
        n_matches=100,
    )
    for name, attack, defense in ((HOME, 0.4, -0.2), (AWAY, -0.4, 0.2), (THIRD, 0.0, 0.0)):
        TeamParam.objects.create(model_run=run, team=teams[name], attack=attack, defense=defense)

    for number, (home, away, goals) in enumerate(
        ((HOME, AWAY, (2, 0)), (THIRD, HOME, (1, 1)), (AWAY, THIRD, (3, 2)))
    ):
        Match.objects.create(
            season="2526",
            date=date(2026, 5, 2 + number),
            home=teams[home],
            away=teams[away],
            home_goals=goals[0],
            away_goals=goals[1],
            ftr="H" if goals[0] > goals[1] else "A" if goals[0] < goals[1] else "D",
        )
    kickoff = (datetime.now(UTC) + timedelta(days=5)).replace(microsecond=0)
    Fixture.objects.create(
        season="2627", matchday=1, kickoff_utc=kickoff, home=teams[HOME], away=teams[THIRD]
    )
    Player.objects.create(
        tm_id=1,
        team=teams[HOME],
        name="Serhou Guirassy",
        position="Centre-Forward",
        market_value_eur=60_000_000,
        scraped_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


@pytest.fixture
def sqlalchemy_engine() -> Iterator[Engine]:
    db = connection.settings_dict
    url = (
        f"postgresql+psycopg://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
    )
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def fastapi_client(
    sqlalchemy_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[list[FakeResponse]], TestClient]]:
    monkeypatch.delenv("PROXY_SECRET", raising=False)
    get_settings.cache_clear()
    limiter.reset()
    factory = make_session_factory(sqlalchemy_engine)

    def session_override() -> Iterator[Session]:
        with factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_session] = session_override

    def build(responses: list[FakeResponse]) -> TestClient:
        fastapi_app.dependency_overrides[get_llm_client] = lambda: ScriptedClient(responses)
        return TestClient(fastapi_app)

    yield build
    fastapi_app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def django_stream(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[FakeResponse]], str]:
    monkeypatch.setattr("accounts.plans.limit_for", lambda user: 1_000)
    api_client = APIClient()
    api_client.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    api_client.force_authenticate(user=User.objects.create_user(username="parity"))

    def stream(responses: list[FakeResponse]) -> str:
        monkeypatch.setattr(
            "predictions.views.get_llm_client", lambda: ScriptedClient(list(responses))
        )
        response = api_client.post("/api/v1/predict/stream", {"query": QUERY}, format="json")
        assert response.status_code == 200, getattr(response, "content", b"")
        assert response["Content-Type"].startswith("text/event-stream")
        return stream_body(response).decode()

    return stream


async def collect_chunks(response: Any) -> bytes:
    return b"".join([chunk async for chunk in response.streaming_content])


def stream_body(response: Any) -> bytes:
    return bytes(async_to_sync(collect_chunks)(response))


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    frames = []
    for chunk in body.strip().split("\n\n"):
        lines = chunk.split("\n")
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        frames.append((event, json.loads(data)))
    return frames


def comparable_stages(frames: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Stage frames minus the one field the two stacks deliberately differ on.

    FastAPI sends the raw tool `payload`; Django sends a short human `summary` instead.
    """
    stages = []
    for event, data in frames:
        if event == "stage":
            stages.append({k: v for k, v in data.items() if k not in ("payload", "summary")})
    return stages


def audit_row_fields(row: Any) -> dict[str, Any]:
    names = (
        "model_run_id home_id away_id match_date query p_home p_draw p_away exp_home_goals "
        "exp_away_goals base_p_home base_p_draw base_p_away adjustments_json explanation"
    ).split()
    return {name: getattr(row, name) for name in names}


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize("name", TRANSCRIPTS)
def test_django_stream_matches_fastapi_stream(
    name: str,
    fastapi_client: Callable[[list[FakeResponse]], TestClient],
    django_stream: Callable[[list[FakeResponse]], str],
    sqlalchemy_engine: Engine,
) -> None:
    transcript = TRANSCRIPTS[name]()

    fastapi_response = fastapi_client(TRANSCRIPTS[name]()).post(
        "/predict/stream", json={"query": QUERY}
    )
    fastapi_frames = parse_sse(fastapi_response.text)
    django_frames = parse_sse(django_stream(transcript))

    assert comparable_stages(django_frames) == comparable_stages(fastapi_frames)
    assert [e for e, _ in django_frames][-1] == "result"
    django_result, fastapi_result = django_frames[-1][1], fastapi_frames[-1][1]
    assert {**django_result, "prediction_id": None} == {**fastapi_result, "prediction_id": None}

    if django_result["prediction_id"] is None:
        assert fastapi_result["prediction_id"] is None
        return
    django_row = Prediction.objects.get(pk=django_result["prediction_id"])
    with make_session_factory(sqlalchemy_engine)() as session:
        fastapi_row = session.get(SqlPrediction, fastapi_result["prediction_id"])
    assert fastapi_row is not None
    assert audit_row_fields(django_row) == audit_row_fields(fastapi_row)


@pytest.mark.usefixtures("seeded")
def test_the_covered_transcripts_exercise_every_kind_of_stage(
    django_stream: Callable[[list[FakeResponse]], str],
) -> None:
    """Guards the parity test against passing on two equally empty streams."""
    seen: set[str] = set()
    oks: set[bool] = set()
    for name in TRANSCRIPTS:
        for event, data in parse_sse(django_stream(TRANSCRIPTS[name]())):
            if event == "stage":
                seen.add(data["name"])
                if data["type"] == "tool_result":
                    oks.add(data["ok"])

    assert {
        "predict_match",
        "predict_match_with_context",
        "get_team_form",
        "lookup_player",
        "get_recent_results",
        "get_upcoming_fixtures",
    } <= seen
    assert oks == {True, False}
