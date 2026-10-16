"""Endpoints that other work will fill in answer 501 with the contract's error body."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

NOT_IMPLEMENTED = {
    "code": "not_implemented",
    "message": "This endpoint is not implemented yet.",
}

CONVERSATION_ID = uuid.UUID(int=1)

# (method, path, json body, needs a session)
STUBS: list[tuple[str, str, dict[str, Any] | None, bool]] = [
    ("post", "/api/v1/predict/stream", {"query": "Bayern v Dortmund"}, True),
    ("get", "/api/v1/me", None, True),
    ("patch", "/api/v1/me", {"email_opt_in": True, "timezone": "America/Toronto"}, True),
    ("get", "/api/v1/conversations", None, True),
    ("get", f"/api/v1/conversations/{CONVERSATION_ID}", None, True),
    ("delete", f"/api/v1/conversations/{CONVERSATION_ID}", None, True),
    ("post", "/api/v1/billing/checkout", None, True),
    ("post", "/api/v1/billing/portal", None, True),
    ("get", "/api/v1/track-record", None, False),
    ("get", "/api/v1/admin/metrics", None, True),
    ("post", "/api/v1/demo/start", None, False),
    ("post", "/api/v1/email/unsubscribe", {"token": "signed-token"}, False),
    ("post", "/stripe/webhook/live", {}, False),
    ("post", "/stripe/webhook/test", {}, False),
]


def _call(client: APIClient, method: str, path: str, body: dict[str, Any] | None) -> Any:
    return getattr(client, method)(path, body, format="json")


@pytest.mark.parametrize(("method", "path", "body", "needs_session"), STUBS)
def test_stub_answers_501_for_a_valid_request(
    signed_in_client: APIClient,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    needs_session: bool,
) -> None:
    response = _call(signed_in_client, method, path, body)

    assert response.status_code == 501
    assert response.json() == NOT_IMPLEMENTED


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [(m, p, b) for m, p, b, needs_session in STUBS if needs_session],
)
def test_session_endpoints_answer_401_without_a_session(
    api_client: APIClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = _call(api_client, method, path, body)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [(m, p, b) for m, p, b, needs_session in STUBS if not needs_session],
)
def test_public_endpoints_need_no_session(
    api_client: APIClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    assert _call(api_client, method, path, body).status_code == 501


@pytest.mark.parametrize("query", ["", "x" * 501])
def test_predict_stream_validates_the_query_before_anything_else(
    signed_in_client: APIClient, query: str
) -> None:
    response = signed_in_client.post("/api/v1/predict/stream", {"query": query}, format="json")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"].startswith("query:")


def test_predict_stream_accepts_a_conversation_and_fixture(signed_in_client: APIClient) -> None:
    body = {"query": "Kane is out", "conversation_id": str(CONVERSATION_ID), "fixture_id": 123}

    response = signed_in_client.post("/api/v1/predict/stream", body, format="json")

    assert response.status_code == 501


def test_predict_stream_rejects_a_malformed_conversation_id(signed_in_client: APIClient) -> None:
    body = {"query": "Kane is out", "conversation_id": "not-a-uuid"}

    response = signed_in_client.post("/api/v1/predict/stream", body, format="json")

    assert response.status_code == 400


def test_me_patch_rejects_an_unknown_time_zone(signed_in_client: APIClient) -> None:
    response = signed_in_client.patch("/api/v1/me", {"timezone": "Mars/Olympus"}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"


def test_unsubscribe_requires_a_token(api_client: APIClient) -> None:
    response = api_client.post("/api/v1/email/unsubscribe", {}, format="json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("token:")


def test_conversation_ids_must_be_uuids(signed_in_client: APIClient) -> None:
    assert signed_in_client.get("/api/v1/conversations/42").status_code == 404
