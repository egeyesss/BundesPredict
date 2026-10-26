"""The two past conversations every new demo user starts with."""

from __future__ import annotations

import socket
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from bundespredict.model.adjust import predict_adjusted
from chat.models import Conversation
from football import repositories
from football.models import Fixture, ModelRun, Player
from football.serializers import markets_payload
from ops import demo
from ops.metrics import build_metrics
from predictions.models import Prediction

pytestmark = pytest.mark.django_db

QUERY_BUDGET = 60


def start_user(**options: Any) -> User:
    return demo.start_demo(client_ip="203.0.113.7", **options)


def card_of(conversation: Conversation) -> dict[str, Any]:
    prediction = conversation.messages.get(role="assistant").prediction
    assert prediction is not None
    assert isinstance(prediction.response_json, dict)
    return prediction.response_json


def seeded(user: User) -> list[Conversation]:
    return list(Conversation.objects.filter(user=user).order_by("created_at", "id"))


def test_a_new_demo_user_gets_two_conversations_pinned_to_upcoming_fixtures(
    demo_world: None,
) -> None:
    user = start_user()

    conversations = seeded(user)

    upcoming = list(Fixture.objects.filter(kickoff_utc__gte=timezone.now()).order_by("kickoff_utc"))
    assert len(conversations) == 2
    assert {c.fixture_id for c in conversations} <= {f.pk for f in upcoming}
    assert len({c.fixture_id for c in conversations}) == 2
    for conversation in conversations:
        roles = list(conversation.messages.values_list("role", flat=True))
        assert roles == ["user", "assistant"]


def test_the_messages_use_the_fixtures_real_team_names_and_a_real_squad_player(
    demo_world: None,
) -> None:
    user = start_user()

    squad = set(Player.objects.values_list("name", flat=True))
    for conversation in seeded(user):
        assert conversation.fixture is not None
        question, answer = conversation.messages.all()
        names = {conversation.fixture.home.name, conversation.fixture.away.name}
        assert any(name in question.content for name in names)
        assert any(name in answer.content for name in names)
        assert any(player in question.content for player in squad)
        assert conversation.title == Conversation.title_for(question.content)


def test_each_answer_is_the_engines_own_adjusted_output(demo_world: None) -> None:
    user = start_user()
    ratings = repositories.ratings_for(ModelRun.objects.get(version="serve"))

    for conversation in seeded(user):
        assistant = conversation.messages.get(role="assistant")
        assert assistant.prediction is not None
        card = card_of(conversation)
        adjustments = [(a["target"], a["requested_magnitude_xg"]) for a in card["adjustments"]]
        expected = predict_adjusted(ratings, card["home"], card["away"], adjustments)
        assert card["adjusted"] == markets_payload(expected)
        assert card["baseline"] == markets_payload(ratings.predict(card["home"], card["away"]))
        assert card["prediction_id"] == assistant.prediction.pk
        assert card["explanation"] == assistant.content


def test_one_conversation_shows_a_clamped_adjustment_and_the_other_an_unclamped_one(
    demo_world: None,
) -> None:
    user = start_user()

    cards = [card_of(c) for c in seeded(user)]

    amounts = sorted(
        (a["requested_magnitude_xg"], a["effective_magnitude_xg"])
        for card in cards
        for a in card["adjustments"]
    )
    clamped = [pair for pair in amounts if pair[0] != pair[1]]
    plain = [pair for pair in amounts if pair[0] == pair[1]]
    assert clamped == [(-0.85, -0.6)]
    assert len(plain) == 1
    assert 0 < abs(plain[0][0]) < 0.6


def test_seeded_predictions_belong_to_the_demo_user_and_carry_no_cost(demo_world: None) -> None:
    user = start_user()

    predictions = list(Prediction.objects.filter(user=user))

    assert len(predictions) == 2
    for prediction in predictions:
        assert prediction.cost_usd is None
        assert prediction.input_tokens is None
        assert prediction.output_tokens is None
        assert prediction.conversation is not None
        assert prediction.model_run_id == ModelRun.objects.get(version="serve").pk


def test_seeded_chats_do_not_show_up_in_admin_cost_numbers(demo_world: None) -> None:
    start_user()

    metrics = build_metrics(days=7, masked=False)

    assert metrics["llm_cost_per_user_cents"] == 0.0
    assert metrics["cost_to_revenue_per_pro_user"] is None


def test_the_conversation_endpoint_renders_the_result_card(demo_world: None) -> None:
    api_client = APIClient(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    api_client.post("/api/v1/demo/start", HTTP_X_CLIENT_IP="203.0.113.7")
    listing = api_client.get("/api/v1/conversations").json()["results"]

    assert len(listing) == 2
    for summary in listing:
        detail = api_client.get(f"/api/v1/conversations/{summary['id']}").json()
        user_message, assistant = detail["messages"]
        prediction = assistant["prediction"]
        assert user_message["prediction"] is None
        assert set(prediction) == {
            "home",
            "away",
            "explanation",
            "baseline",
            "adjusted",
            "adjustments",
            "prediction_id",
        }
        assert prediction["adjustments"][0]["rationale"]


def test_without_upcoming_fixtures_the_most_recent_played_ones_are_used(demo_world: None) -> None:
    Fixture.objects.filter(kickoff_utc__gte=timezone.now()).update(
        kickoff_utc=timezone.now() - timedelta(days=2)
    )
    newest = list(Fixture.objects.order_by("-kickoff_utc", "-id")[:2])

    user = start_user()

    assert {c.fixture_id for c in seeded(user)} == {f.pk for f in newest}


def test_a_squad_less_club_still_gets_a_conversation(demo_world: None) -> None:
    Player.objects.all().delete()

    user = start_user()

    assert len(seeded(user)) == 2


def test_no_serving_run_means_no_seeded_chats_but_the_account_still_starts() -> None:
    user = start_user()

    assert seeded(user) == []
    assert user.profile.is_demo


@pytest.fixture
def only_database_traffic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any socket connection other than the one to Postgres fails the test."""
    database_port = int(str(settings.DATABASES["default"]["PORT"]))
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> None:
        if not (isinstance(address, tuple) and address[1] == database_port):
            raise AssertionError(f"unexpected network call to {address!r}")
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


def test_seeding_makes_no_network_calls_and_stays_within_a_query_budget(
    demo_world: None, only_database_traffic: None
) -> None:
    with CaptureQueriesContext(connection) as captured:
        start_user()

    assert len(captured) <= QUERY_BUDGET
