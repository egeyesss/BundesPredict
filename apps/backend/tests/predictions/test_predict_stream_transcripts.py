"""Each scripted transcript streams its recorded stages and result and stores its audit row.

`recorded/stream_transcripts.json` holds the stage frames, the final `result` frame and the
persisted `Prediction` fields for each transcript below. Re-record it deliberately when the agent's
behaviour is meant to change.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from tests.agent.fakes import (
    FakeResponse,
    FakeTextBlock,
    FakeToolUseBlock,
    ScriptedClient,
    transcript_full,
    transcript_refusal,
)

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
def stream_transcript(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[FakeResponse]], str]:
    monkeypatch.setattr("accounts.plans.limit_for", lambda *args, **kwargs: 1_000)
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


def audit_row_fields(row: Prediction) -> dict[str, Any]:
    """The stored row with ids replaced by what they point at, so it compares across databases."""
    names = (
        "match_date query p_home p_draw p_away exp_home_goals exp_away_goals base_p_home "
        "base_p_draw base_p_away adjustments_json explanation"
    ).split()
    fields = {name: getattr(row, name) for name in names}
    fields["match_date"] = None if row.match_date is None else row.match_date.isoformat()
    return {**fields, "home": row.home.name, "away": row.away.name}


def assert_close(actual: Any, expected: Any) -> None:
    """Equality with a float tolerance, so a recording from one platform holds on another."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys()
        for key, value in expected.items():
            assert_close(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            assert_close(actual_item, expected_item)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=1e-9)
    else:
        assert actual == expected


RECORDED = json.loads((Path(__file__).parent / "recorded" / "stream_transcripts.json").read_text())


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize("name", TRANSCRIPTS)
def test_stream_matches_the_recording(
    name: str, stream_transcript: Callable[[list[FakeResponse]], str]
) -> None:
    recorded = RECORDED[name]

    frames = parse_sse(stream_transcript(TRANSCRIPTS[name]()))

    assert_close([data for event, data in frames if event == "stage"], recorded["stages"])
    assert frames[-1][0] == "result"
    result = {**frames[-1][1]}
    prediction_id = result.pop("prediction_id")
    assert_close(result, recorded["result"])
    if recorded["audit"] is None:
        assert prediction_id is None
        return
    row = Prediction.objects.select_related("home", "away").get(pk=prediction_id)
    assert row.model_run_id == ModelRun.objects.get(version="serve").id
    assert_close(audit_row_fields(row), recorded["audit"])


@pytest.mark.usefixtures("seeded")
def test_the_covered_transcripts_exercise_every_kind_of_stage(
    stream_transcript: Callable[[list[FakeResponse]], str],
) -> None:
    """Guards the recording against going stale into streams that cover less than it claims."""
    seen: set[str] = set()
    oks: set[bool] = set()
    for name in TRANSCRIPTS:
        for event, data in parse_sse(stream_transcript(TRANSCRIPTS[name]())):
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
