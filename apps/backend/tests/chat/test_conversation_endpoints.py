"""Conversation list, detail and delete: ownership, ordering, pagination, cross-browser resume."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client
from rest_framework.test import APIClient
from tests.agent.fakes import FakeResponse, FakeTextBlock, ScriptedClient, transcript_full

from chat.models import Conversation, Message
from football.models import Match, ModelRun, Team, TeamParam
from predictions.models import Prediction
from predictions.throttles import throttle_cache

pytestmark = pytest.mark.django_db(transaction=True)

LIST_URL = "/api/v1/conversations"
HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
AUTH = "/_allauth/browser/v1/auth"
CODE_LINE = re.compile(r"^\s*([A-Z0-9]{4}-[A-Z0-9]{4})\s*$", re.MULTILINE)


@pytest.fixture(autouse=True)
def _empty_throttle() -> Iterator[None]:
    throttle_cache.clear()
    yield
    throttle_cache.clear()


def signed_in(user: User) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="reader", email="reader@example.com")


@pytest.fixture
def other() -> User:
    return User.objects.create_user(username="other", email="other@example.com")


@pytest.fixture
def client(user: User) -> APIClient:
    return signed_in(user)


def conversation_at(user: User, title: str, when: datetime) -> Conversation:
    conversation = Conversation.objects.create(user=user, title=title)
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=when)
    return conversation


def test_every_conversation_endpoint_needs_a_session() -> None:
    anonymous = APIClient()
    anonymous.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    detail = f"{LIST_URL}/{uuid.uuid4()}"

    responses = [anonymous.get(LIST_URL), anonymous.get(detail), anonymous.delete(detail)]

    assert [r.status_code for r in responses] == [401, 401, 401]
    assert {r.json()["code"] for r in responses} == {"not_authenticated"}


def test_the_list_is_newest_first_and_only_the_callers(
    client: APIClient, user: User, other: User
) -> None:
    noon = datetime(2026, 10, 1, 12, tzinfo=UTC)
    old = conversation_at(user, "older", noon)
    new = conversation_at(user, "newer", noon + timedelta(hours=1))
    conversation_at(other, "not mine", noon + timedelta(hours=2))

    body = client.get(LIST_URL).json()

    assert [c["id"] for c in body["results"]] == [str(new.id), str(old.id)]
    assert body["next"] is None
    assert set(body["results"][0]) == {"id", "title", "fixture_id", "updated_at"}


def test_an_empty_list_is_an_empty_page(client: APIClient) -> None:
    assert client.get(LIST_URL).json() == {"next": None, "results": []}


def test_pages_follow_the_opaque_cursor_without_gaps_or_repeats(
    client: APIClient, user: User
) -> None:
    start = datetime(2026, 10, 1, tzinfo=UTC)
    made = [conversation_at(user, f"chat {i}", start + timedelta(minutes=i)) for i in range(5)]
    expected = [str(c.id) for c in reversed(made)]

    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        params = {"limit": "2", **({"cursor": cursor} if cursor else {})}
        body = client.get(LIST_URL, params).json()
        seen += [c["id"] for c in body["results"]]
        pages += 1
        cursor = body["next"]
        if cursor is None:
            break

    assert seen == expected
    assert pages == 3
    assert "://" not in str(body)


@pytest.mark.parametrize("limit", ["0", "-1", "abc", "51"])
def test_a_limit_outside_one_to_fifty_is_a_400_or_clamped(client: APIClient, limit: str) -> None:
    response = client.get(LIST_URL, {"limit": limit})

    assert response.status_code in (200, 400)
    if response.status_code == 200:
        assert len(response.json()["results"]) <= 50


def test_a_garbage_cursor_is_a_404_not_a_server_error(client: APIClient) -> None:
    assert client.get(LIST_URL, {"cursor": "not-a-cursor"}).status_code == 404


def seed_prediction(user: User, conversation: Conversation) -> Prediction:
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
    return Prediction.objects.create(
        user=user,
        conversation=conversation,
        model_run=run,
        home=teams[HOME],
        away=teams[AWAY],
        p_home=0.5,
        p_draw=0.3,
        p_away=0.2,
        exp_home_goals=1.6,
        exp_away_goals=1.0,
        base_p_home=0.5,
        base_p_draw=0.3,
        base_p_away=0.2,
    )


def test_the_detail_lists_messages_in_order_with_the_prediction_attached(
    client: APIClient, user: User
) -> None:
    conversation = Conversation.objects.create(user=user, title="Kane")
    prediction = seed_prediction(user, conversation)
    payload: dict[str, Any] = {
        "home": HOME,
        "away": AWAY,
        "explanation": "Close call.",
        "baseline": None,
        "adjusted": None,
        "adjustments": [],
        "prediction_id": prediction.id,
    }
    Prediction.objects.filter(pk=prediction.pk).update(response_json=payload)
    Message.objects.create(conversation=conversation, role="user", content="Kane is out")
    Message.objects.create(
        conversation=conversation,
        role="assistant",
        content="Close call.",
        prediction=prediction,
    )

    body = client.get(f"{LIST_URL}/{conversation.id}").json()

    assert body["id"] == str(conversation.id)
    assert body["title"] == "Kane"
    assert [(m["role"], m["content"]) for m in body["messages"]] == [
        ("user", "Kane is out"),
        ("assistant", "Close call."),
    ]
    assert body["messages"][0]["prediction"] is None
    assert body["messages"][1]["prediction"] == payload
    assert set(body["messages"][0]) == {"id", "role", "content", "prediction", "created_at"}


def test_someone_elses_conversation_is_a_404_on_detail_and_delete(
    client: APIClient, other: User
) -> None:
    theirs = Conversation.objects.create(user=other, title="private")
    Message.objects.create(conversation=theirs, role="user", content="secret")

    detail = client.get(f"{LIST_URL}/{theirs.id}")
    deleted = client.delete(f"{LIST_URL}/{theirs.id}")

    assert (detail.status_code, deleted.status_code) == (404, 404)
    assert detail.json()["code"] == "not_found"
    assert "secret" not in detail.content.decode()
    assert Conversation.objects.filter(pk=theirs.pk).exists()
    assert Message.objects.count() == 1


def test_a_conversation_id_must_be_a_uuid(client: APIClient) -> None:
    assert client.get(f"{LIST_URL}/42").status_code == 404


def test_an_unknown_conversation_is_a_404(client: APIClient) -> None:
    missing = f"{LIST_URL}/{uuid.uuid4()}"

    assert client.get(missing).status_code == 404
    assert client.delete(missing).status_code == 404


def test_delete_removes_the_conversation_and_messages_but_keeps_the_audit_row(
    client: APIClient, user: User
) -> None:
    conversation = Conversation.objects.create(user=user, title="gone soon")
    prediction = seed_prediction(user, conversation)
    Message.objects.create(conversation=conversation, role="user", content="hi")
    Message.objects.create(
        conversation=conversation, role="assistant", content="yo", prediction=prediction
    )

    response = client.delete(f"{LIST_URL}/{conversation.id}")

    assert response.status_code == 204
    assert Conversation.objects.count() == 0
    assert Message.objects.count() == 0
    kept = Prediction.objects.get()
    assert kept.conversation is None
    assert kept.user == user
    assert client.get(f"{LIST_URL}/{conversation.id}").status_code == 404


def _registered(username: str, email: str) -> User:
    user = User.objects.create_user(username=username, email=email)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def _post(browser: Client, path: str, body: dict[str, Any]) -> Any:
    return browser.post(f"{AUTH}/{path}", body, content_type="application/json")


def sign_in_with_code(browser: Client, email: str) -> None:
    _post(browser, "code/request", {"email": email})
    match = CODE_LINE.search(str(mail.outbox[-1].body))
    assert match, mail.outbox[-1].body
    confirmed = _post(browser, "code/confirm", {"code": match.group(1)})
    assert confirmed.json()["meta"]["is_authenticated"] is True


async def _drain(response: Any) -> bytes:
    return b"".join([chunk async for chunk in response.streaming_content])


def test_a_conversation_started_in_one_browser_resumes_in_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _registered("grace", "grace@example.com")
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
    laptop = Client(headers={"x-proxy-secret": settings.PROXY_SECRET})
    phone = Client(headers={"x-proxy-secret": settings.PROXY_SECRET})
    sign_in_with_code(laptop, "grace@example.com")
    scripts: list[ScriptedClient] = []

    def scripted(responses: list[FakeResponse]) -> None:
        def make() -> ScriptedClient:
            scripts.append(ScriptedClient(list(responses)))
            return scripts[-1]

        monkeypatch.setattr("predictions.views.get_llm_client", make)

    scripted(transcript_full(HOME, AWAY))
    started = laptop.post(
        "/api/v1/predict/stream",
        {"query": "striker out, windy"},
        content_type="application/json",
    )
    first_frame = bytes(async_to_sync(_drain)(started)).decode().split("\n\n")[0]
    conversation_id = json.loads(first_frame.split("data: ", 1)[1])["id"]

    sign_in_with_code(phone, "grace@example.com")
    listed = phone.get(LIST_URL).json()
    detail = phone.get(f"{LIST_URL}/{conversation_id}").json()
    scripted([FakeResponse([FakeTextBlock("Still close.")], "end_turn")])
    resumed = phone.post(
        "/api/v1/predict/stream",
        {"query": "and if he plays?", "conversation_id": conversation_id},
        content_type="application/json",
    )
    async_to_sync(_drain)(resumed)

    assert [c["id"] for c in listed["results"]] == [conversation_id]
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["prediction"]["home"] == HOME
    assert scripts[-1].messages.calls[0]["messages"][0] == {
        "role": "user",
        "content": "striker out, windy",
    }
    assert Message.objects.filter(conversation_id=conversation_id).count() == 4
