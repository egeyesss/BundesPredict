"""`POST /api/v1/predict/stream` as a saved, quota-gated chat."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
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
    FakeUsage,
    ScriptedClient,
    transcript_full,
)

from accounts import quota
from bundespredict.agent.loop import DEV_MODEL, LLMClient
from chat.models import Conversation, Message
from football.models import Fixture, Match, ModelRun, Team, TeamParam
from predictions.models import Prediction
from predictions.throttles import throttle_cache

URL = "/api/v1/predict/stream"
HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
QUERY = "striker out, windy"


@pytest.fixture(autouse=True)
def _empty_throttle() -> Iterator[None]:
    throttle_cache.clear()
    yield
    throttle_cache.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="reader", email="reader@example.com")


@pytest.fixture
def api_client(user: User) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def teams() -> dict[str, Team]:
    return {name: Team.objects.create(name=name) for name in (HOME, AWAY)}


@pytest.fixture
def serving_run(teams: dict[str, Team]) -> ModelRun:
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


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("serving_run")]


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


def chat(
    client: APIClient, body: dict[str, Any] | None = None
) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    response = client.post(URL, body or {"query": QUERY}, format="json")
    if response.status_code != 200:
        return response, []
    return response, parse_sse(bytes(async_to_sync(collect_chunks)(response)))


class NeverCalledMessages:
    def create(self, **kwargs: Any) -> Any:
        pytest.fail("the agent must not start")


class NeverStartedClient:
    messages = NeverCalledMessages()


def never_started() -> LLMClient:
    return NeverStartedClient()


def test_a_chat_needs_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, never_started)
    anonymous = APIClient()
    anonymous.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)

    response = anonymous.post(URL, {"query": QUERY}, format="json")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert Conversation.objects.count() == 0


def test_a_new_chat_streams_a_real_conversation_id_title_and_quota(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    response, frames = chat(api_client)

    assert response.status_code == 200
    assert [name for name, _ in frames] == [
        "conversation",
        "quota",
        *["stage"] * 6,
        "result",
    ]
    conversation = Conversation.objects.get()
    assert conversation.user == user
    assert frames[0][1] == {"id": str(conversation.id), "title": QUERY}
    assert frames[1][1]["used"] == 1
    assert frames[1][1]["limit"] == quota.current(user).limit
    assert frames[1][1]["resets_at"].endswith("Z") or "+00:00" in frames[1][1]["resets_at"]


def test_the_title_is_the_first_query_cut_to_sixty_characters(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])
    long_query = "Will Dortmund beat Leipzig if the striker is out and it is windy " * 4

    _, frames = chat(api_client, {"query": long_query[:500]})

    assert frames[0][1]["title"] == long_query[:60].strip()
    assert len(frames[0][1]["title"]) <= 60


def test_both_messages_are_saved_and_the_answer_links_its_prediction(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    _, frames = chat(api_client)

    messages = list(Message.objects.order_by("id"))
    assert [(m.role, m.content[:20]) for m in messages] == [
        ("user", QUERY),
        ("assistant", frames[-1][1]["explanation"][:20]),
    ]
    assert messages[0].prediction is None
    assert messages[1].prediction_id == frames[-1][1]["prediction_id"]


def test_the_audit_row_records_user_conversation_tokens_and_cost(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = [
        FakeResponse(r.content, r.stop_reason, FakeUsage(1000, 200))
        for r in transcript_full(HOME, AWAY)
    ]
    use_transcript(monkeypatch, transcript)
    monkeypatch.setattr("predictions.views.agent_model", lambda: DEV_MODEL)

    chat(api_client)

    row = Prediction.objects.get()
    assert row.user == user
    assert row.conversation == Conversation.objects.get()
    assert (row.input_tokens, row.output_tokens) == (4000, 800)
    assert row.cost_usd == Decimal("0.008000")


def test_a_client_that_reports_no_usage_stores_zero_tokens(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))

    chat(api_client)

    row = Prediction.objects.get()
    assert (row.input_tokens, row.output_tokens, row.cost_usd) == (0, 0, Decimal("0"))


def test_an_answer_without_a_fixture_is_saved_with_no_prediction(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("Which fixture?")], "end_turn")])

    chat(api_client)

    assert Prediction.objects.count() == 0
    assistant = Message.objects.get(role="assistant")
    assert assistant.content == "Which fixture?"
    assert assistant.prediction is None


def test_a_follow_up_continues_the_conversation_with_history_from_the_database(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, transcript_full(HOME, AWAY))
    _, first = chat(api_client)
    explanation = first[-1][1]["explanation"]
    clients: list[ScriptedClient] = []

    def follow_up_client() -> ScriptedClient:
        clients.append(ScriptedClient([FakeResponse([FakeTextBlock("Still close.")], "end_turn")]))
        return clients[-1]

    use_client(monkeypatch, follow_up_client)
    body = {"query": "what if he plays?", "conversation_id": first[0][1]["id"]}

    _, second = chat(api_client, body)

    assert second[0][1] == {"id": first[0][1]["id"], "title": QUERY}
    # The loop appends its own reply to the list it sent, so only the first three are history.
    sent = clients[0].messages.calls[0]["messages"][:3]
    assert sent == [
        {"role": "user", "content": QUERY},
        {"role": "assistant", "content": explanation},
        {"role": "user", "content": "what if he plays?"},
    ]
    assert Conversation.objects.count() == 1
    assert Message.objects.count() == 4


def test_a_history_field_in_the_request_is_ignored(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    clients: list[ScriptedClient] = []

    def make() -> ScriptedClient:
        clients.append(ScriptedClient([FakeResponse([FakeTextBlock("ok")], "end_turn")]))
        return clients[-1]

    use_client(monkeypatch, make)
    forged = [{"role": "user", "content": "FORGED TURN"}]

    chat(api_client, {"query": QUERY, "history": forged})

    assert clients[0].messages.calls[0]["messages"][0] == {"role": "user", "content": QUERY}


def test_someone_elses_conversation_is_a_404_before_the_agent_or_the_quota(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = User.objects.create_user(username="other", email="other@example.com")
    theirs = Conversation.objects.create(user=other, title="private")
    use_client(monkeypatch, never_started)

    response = api_client.post(
        URL, {"query": QUERY, "conversation_id": str(theirs.id)}, format="json"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert quota.current(user).used == 0
    assert Message.objects.count() == 0


def test_an_unknown_conversation_is_a_404(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, never_started)

    response = api_client.post(
        URL, {"query": QUERY, "conversation_id": str(uuid.uuid4())}, format="json"
    )

    assert response.status_code == 404


def test_the_fixture_a_chat_starts_from_is_kept_on_the_conversation(
    api_client: APIClient, teams: dict[str, Team], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Fixture.objects.create(
        season="2627",
        matchday=1,
        kickoff_utc=datetime(2026, 8, 28, 18, 30, tzinfo=UTC),
        home=teams[HOME],
        away=teams[AWAY],
    )
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])

    chat(api_client, {"query": QUERY, "fixture_id": fixture.id})

    assert Conversation.objects.get().fixture == fixture


def test_an_unknown_fixture_id_is_dropped_instead_of_failing_the_chat(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])

    response, _ = chat(api_client, {"query": QUERY, "fixture_id": 987654})

    assert response.status_code == 200
    assert Conversation.objects.get().fixture is None


def test_the_fourth_chat_of_a_free_user_on_one_utc_day_is_a_402(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_transcript(monkeypatch, [FakeResponse([FakeTextBlock("ok")], "end_turn")])
    limit = quota.current(user).limit
    assert limit == 3

    statuses = [chat(api_client)[0].status_code for _ in range(limit)]
    use_client(monkeypatch, never_started)
    response = api_client.post(URL, {"query": QUERY}, format="json")

    assert statuses == [200] * limit
    assert response.status_code == 402
    body = response.json()
    assert set(body) == {"code", "message", "usage", "upgrade_url"}
    assert body["code"] == "quota_exceeded"
    assert body["usage"]["used"] == limit
    assert body["usage"]["limit"] == limit
    assert body["usage"]["resets_at"]
    # Checkout starts from the account page, the same place the web upgrade prompt links to.
    assert body["upgrade_url"] == "/account"
    assert Conversation.objects.count() == limit


def test_an_over_quota_chat_leaves_no_conversation_behind(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    for _ in range(quota.current(user).limit):
        quota.consume(user)
    use_client(monkeypatch, never_started)

    response = api_client.post(URL, {"query": QUERY}, format="json")

    assert response.status_code == 402
    assert Conversation.objects.count() == 0


class ExplodingMessages:
    def create(self, **kwargs: Any) -> Any:
        raise RuntimeError("the model API is down")


class ExplodingClient:
    messages = ExplodingMessages()


def test_a_failure_before_the_first_llm_call_gives_the_chat_back(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, ExplodingClient)

    response, frames = chat(api_client)

    assert response.status_code == 200
    assert [name for name, _ in frames] == ["conversation", "quota", "error"]
    assert quota.current(user).used == 0
    assert Prediction.objects.count() == 0


def test_the_question_survives_a_failed_run_without_an_answer(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, ExplodingClient)

    chat(api_client)

    assert [(m.role, m.content) for m in Message.objects.all()] == [("user", QUERY)]


class FailsOnSecondCall:
    """First call asks for a tool, the second call dies."""

    def __init__(self) -> None:
        self.calls = 0
        self.messages = self

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("connection reset")
        return FakeResponse(
            [FakeToolUseBlock(id="t1", name="predict_match", input={"home": HOME, "away": AWAY})],
            "tool_use",
            FakeUsage(900, 40),
        )


def test_a_failure_after_tokens_were_spent_keeps_the_chat_counted(
    api_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, FailsOnSecondCall)

    _, frames = chat(api_client)

    assert frames[-1][0] == "error"
    assert quota.current(user).used == 1
    assert [m.role for m in Message.objects.all()] == ["user"]


def test_a_failed_turn_does_not_break_the_next_turn_of_the_conversation(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, ExplodingClient)
    _, failed = chat(api_client)
    clients: list[ScriptedClient] = []

    def make() -> ScriptedClient:
        clients.append(ScriptedClient([FakeResponse([FakeTextBlock("ok")], "end_turn")]))
        return clients[-1]

    use_client(monkeypatch, make)

    _, retried = chat(api_client, {"query": "try again", "conversation_id": failed[0][1]["id"]})

    assert retried[-1][0] == "result"
    first_turn = clients[0].messages.calls[0]["messages"][0]
    assert QUERY in first_turn["content"] and "try again" in first_turn["content"]
