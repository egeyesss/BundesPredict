"""`POST /api/v1/predict/stream`: framing, flushing, failures and the per-IP throttle."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import User
from django.test import AsyncClient
from rest_framework.test import APIClient
from tests.agent.fakes import (
    FakeResponse,
    FakeTextBlock,
    FakeToolUseBlock,
    ScriptedClient,
    transcript_full,
)

from app.security import PREDICT_RATE_LIMIT as FASTAPI_RATE_LIMIT
from bundespredict.agent.loop import LLMClient
from football.models import Match, ModelRun, Team, TeamParam
from predictions.models import Prediction
from predictions.throttles import PREDICT_RATE_LIMIT, throttle_cache

pytestmark = pytest.mark.django_db(transaction=True)

URL = "/api/v1/predict/stream"
HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
BODY = {"query": "striker out, windy"}
HOURLY_LIMIT = int(PREDICT_RATE_LIMIT.split("/")[0])


@pytest.fixture(autouse=True)
def _empty_throttle() -> Iterator[None]:
    throttle_cache.clear()
    yield
    throttle_cache.clear()


@pytest.fixture
def signed_in_user() -> User:
    return User.objects.create_user(username="reader", email="reader@example.com")


@pytest.fixture(autouse=True)
def _no_daily_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests exercise streaming and the hourly throttle, not the daily quota."""
    monkeypatch.setattr("accounts.plans.limit_for", lambda user: 1_000)


@pytest.fixture
def api_client(signed_in_user: User) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    client.force_authenticate(user=signed_in_user)
    return client


@pytest.fixture
def serving_run() -> ModelRun:
    teams = {name: Team.objects.create(name=name) for name in (HOME, AWAY)}
    run = ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0018,
        rho=-0.12,
        home_adv=0.3,
        log_likelihood=-1.0,
        n_matches=100,
    )
    for name, attack, defense in ((HOME, 0.4, -0.2), (AWAY, -0.4, 0.2)):
        TeamParam.objects.create(model_run=run, team=teams[name], attack=attack, defense=defense)
    Match.objects.create(
        season="2526",
        date=datetime(2026, 5, 2, tzinfo=UTC).date(),
        home=teams[HOME],
        away=teams[AWAY],
        home_goals=2,
        away_goals=0,
        ftr="H",
    )
    return run


def use_client(monkeypatch: pytest.MonkeyPatch, make_client: Callable[[], LLMClient]) -> None:
    monkeypatch.setattr("predictions.views.get_llm_client", make_client)


def use_transcript(monkeypatch: pytest.MonkeyPatch, transcript: list[FakeResponse]) -> None:
    use_client(monkeypatch, lambda: ScriptedClient(list(transcript)))


def parse_sse(body: bytes) -> list[tuple[str, dict[str, Any]]]:
    frames = []
    for chunk in body.decode().strip().split("\n\n"):
        lines = chunk.split("\n")
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        frames.append((event, json.loads(data)))
    return frames


async def collect_chunks(response: Any) -> bytes:
    return b"".join([chunk async for chunk in response.streaming_content])


def stream_body(response: Any) -> bytes:
    return bytes(async_to_sync(collect_chunks)(response))


@pytest.mark.usefixtures("serving_run")
def test_streams_conversation_quota_then_one_stage_per_step_then_result(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    response = api_client.post(URL, BODY, format="json")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"
    frames = parse_sse(stream_body(response))
    assert [name for name, _ in frames] == ["conversation", "quota", *["stage"] * 6, "result"]
    assert frames[0][1]["title"] == BODY["query"]
    stages = [data for name, data in frames if name == "stage"]
    assert [(s["type"], s["name"]) for s in stages] == [
        ("tool_call", "predict_match"),
        ("tool_result", "predict_match"),
        ("tool_call", "lookup_player"),
        ("tool_result", "lookup_player"),
        ("tool_call", "predict_match_with_context"),
        ("tool_result", "predict_match_with_context"),
    ]
    result = frames[-1][1]
    assert result["home"] == HOME and result["away"] == AWAY
    assert result["adjusted"]["p_home"] < result["baseline"]["p_home"]
    assert len(result["adjustments"]) == 2


@pytest.mark.usefixtures("serving_run")
def test_tool_results_carry_a_short_summary_and_never_the_raw_payload(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    frames = parse_sse(stream_body(api_client.post(URL, BODY, format="json")))

    results = [data for name, data in frames if name == "stage" and data["type"] == "tool_result"]
    assert all(set(r) == {"type", "name", "ok", "summary"} for r in results)
    assert all(r["ok"] and 0 < len(r["summary"]) <= 200 for r in results)
    assert "%" in results[0]["summary"]


@pytest.mark.usefixtures("serving_run")
def test_a_failed_tool_is_reported_as_not_ok_with_the_reason(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = [
        FakeResponse(
            content=[
                FakeToolUseBlock(
                    id="t1", name="predict_match", input={"home": "Atlantis FC", "away": AWAY}
                )
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(content=[FakeTextBlock("No such club.")], stop_reason="end_turn"),
    ]
    use_transcript(monkeypatch, transcript)

    frames = parse_sse(stream_body(api_client.post(URL, BODY, format="json")))

    failed = next(data for name, data in frames if data.get("type") == "tool_result")
    assert failed["ok"] is False
    assert "Atlantis FC" in failed["summary"]


@pytest.mark.usefixtures("serving_run")
def test_the_answer_is_stored_as_an_audit_row(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    frames = parse_sse(stream_body(api_client.post(URL, BODY, format="json")))

    row = Prediction.objects.get()
    assert frames[-1][1]["prediction_id"] == row.id
    assert row.query == BODY["query"]
    assert row.model_run.version == "serve"
    assert len(row.adjustments_json) == 2


@pytest.mark.usefixtures("serving_run")
def test_an_answer_without_a_fixture_stores_nothing(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(
        monkeypatch,
        [FakeResponse(content=[FakeTextBlock("Which fixture?")], stop_reason="end_turn")],
    )

    frames = parse_sse(stream_body(api_client.post(URL, BODY, format="json")))

    assert [name for name, _ in frames] == ["conversation", "quota", "result"]
    assert frames[-1][1]["prediction_id"] is None
    assert Prediction.objects.count() == 0


class ExplodingMessages:
    def create(self, **kwargs: Any) -> Any:
        raise RuntimeError("the model API is down")


class ExplodingClient:
    messages = ExplodingMessages()


@pytest.mark.usefixtures("serving_run")
def test_a_failure_after_the_stream_started_arrives_as_an_error_frame(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, ExplodingClient)

    response = api_client.post(URL, BODY, format="json")

    assert response.status_code == 200
    frames = parse_sse(stream_body(response))
    assert [name for name, _ in frames] == ["conversation", "quota", "error"]
    assert set(frames[-1][1]) == {"code", "message"}
    assert frames[-1][1]["code"] == "prediction_failed"
    assert "down" not in frames[-1][1]["message"]
    assert Prediction.objects.count() == 0


def test_without_a_serving_fit_the_answer_is_a_503_before_any_stream(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [])
    ModelRun.objects.create(
        model_type="dixon_coles",
        version="walk-forward",
        xi=0.0,
        rho=0.0,
        home_adv=0.0,
        log_likelihood=0.0,
        n_matches=1,
    )

    response = api_client.post(URL, BODY, format="json")

    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"


@pytest.mark.usefixtures("serving_run")
def test_without_an_api_key_the_answer_is_a_503(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = api_client.post(URL, BODY, format="json")

    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"
    assert "ANTHROPIC_API_KEY" in response.json()["message"]


@pytest.mark.parametrize("query", ["", "x" * 501])
def test_the_query_is_validated_before_anything_runs(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    use_client(monkeypatch, lambda: pytest.fail("the agent must not start"))

    response = api_client.post(URL, {"query": query}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"
    assert response.json()["message"].startswith("query:")


def test_a_malformed_conversation_id_is_rejected(api_client: APIClient) -> None:
    body = {"query": "Kane is out", "conversation_id": "not-a-uuid"}

    assert api_client.post(URL, body, format="json").status_code == 400


@pytest.mark.usefixtures("serving_run")
def test_a_browser_asking_for_an_event_stream_is_not_turned_away(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    response = api_client.post(URL, BODY, format="json", headers={"Accept": "text/event-stream"})

    assert response.status_code == 200
    stream_body(response)


def test_requests_without_the_proxy_secret_are_refused() -> None:
    response = APIClient().post(URL, BODY, format="json")

    assert response.status_code == 403


class SlowScriptedMessages:
    """Sleeps like a real model call and logs when each call returns."""

    def __init__(self, responses: list[FakeResponse], log: list[str], delay: float) -> None:
        self._responses = list(responses)
        self._log = log
        self._delay = delay

    def create(self, **kwargs: Any) -> FakeResponse:
        time.sleep(self._delay)
        self._log.append("llm")
        return self._responses.pop(0)


class SlowClient:
    def __init__(self, responses: list[FakeResponse], log: list[str], delay: float = 0.05) -> None:
        self.messages = SlowScriptedMessages(responses, log, delay)


@pytest.mark.usefixtures("serving_run")
def test_each_frame_is_flushed_before_the_agent_finishes(
    monkeypatch: pytest.MonkeyPatch, signed_in_user: User
) -> None:
    """The first stage frame must reach the client while later LLM calls are still ahead."""
    log: list[str] = []
    use_client(monkeypatch, lambda: SlowClient(transcript_full(HOME, AWAY), log))

    async def consume() -> None:
        browser = AsyncClient()
        await browser.aforce_login(signed_in_user)
        response = await browser.post(
            URL,
            BODY,
            content_type="application/json",
            headers={"x-proxy-secret": settings.PROXY_SECRET},
        )
        assert response.status_code == 200
        async for chunk in response.streaming_content:  # type: ignore[attr-defined]
            event = chunk.decode().split("\n", 1)[0].removeprefix("event: ")
            log.append(f"frame:{event}")

    async_to_sync(consume)()

    llm_calls = [i for i, entry in enumerate(log) if entry == "llm"]
    first_stage = log.index("frame:stage")
    assert log[0] == "frame:conversation"
    assert log[1] == "frame:quota"
    assert len(llm_calls) == 4
    assert llm_calls[0] < first_stage < llm_calls[1]
    assert llm_calls[-1] < log.index("frame:result")


@pytest.mark.usefixtures("serving_run")
def test_the_hourly_limit_is_enforced_per_client_ip(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])

    statuses = [
        api_client.post(
            URL, BODY, format="json", headers={"x-client-ip": "203.0.113.7"}
        ).status_code
        for _ in range(HOURLY_LIMIT + 1)
    ]
    other_ip = api_client.post(URL, BODY, format="json", headers={"x-client-ip": "203.0.113.8"})

    assert statuses == [200] * HOURLY_LIMIT + [429]
    assert other_ip.status_code == 200


@pytest.mark.usefixtures("serving_run")
def test_a_throttled_request_gets_the_contract_error_and_never_reaches_the_agent(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])
    headers = {"x-client-ip": "203.0.113.9"}
    for _ in range(HOURLY_LIMIT):
        api_client.post(URL, BODY, format="json", headers=headers)
    use_client(monkeypatch, lambda: pytest.fail("a throttled request must not reach the agent"))

    response = api_client.post(URL, BODY, format="json", headers=headers)

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert int(response["Retry-After"]) > 0


def test_the_limit_matches_the_one_fastapi_enforces() -> None:
    assert PREDICT_RATE_LIMIT == FASTAPI_RATE_LIMIT


@pytest.mark.usefixtures("serving_run")
def test_without_the_client_ip_header_the_socket_address_is_the_key(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])

    statuses = [
        api_client.post(URL, BODY, format="json", REMOTE_ADDR="198.51.100.4").status_code
        for _ in range(HOURLY_LIMIT + 1)
    ]

    assert statuses[-1] == 429
