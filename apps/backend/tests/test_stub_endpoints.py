"""Endpoints that other work will fill in answer 501 with the contract's error body."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

NOT_IMPLEMENTED = {
    "code": "not_implemented",
    "message": "This endpoint is not implemented yet.",
}

# (method, path, json body, needs a session)
STUBS: list[tuple[str, str, dict[str, Any] | None, bool]] = [
    ("get", "/api/v1/track-record", None, False),
    ("get", "/api/v1/admin/metrics", None, True),
    ("post", "/api/v1/demo/start", None, False),
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
