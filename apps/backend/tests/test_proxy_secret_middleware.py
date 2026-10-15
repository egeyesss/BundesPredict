from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, override_settings

from config.middleware import PROXY_SECRET_HEADER, proxy_secret_middleware

SECRET = "correct-horse-battery-staple"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _configured_secret() -> Iterator[None]:
    with override_settings(PROXY_SECRET=SECRET):
        yield


def _status(client: Client, path: str, secret: str | None = None, method: str = "get") -> int:
    headers = {} if secret is None else {PROXY_SECRET_HEADER: secret}
    return int(getattr(client, method)(path, headers=headers).status_code)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/teams",
        "/api/v1/predict/stream",
        "/api/anything",
        "/_allauth/browser/v1/auth/session",
    ],
)
def test_gated_paths_reject_a_missing_secret(client: Client, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


@pytest.mark.parametrize("path", ["/api/v1/teams", "/_allauth/browser/v1/auth/session"])
def test_gated_paths_reject_a_wrong_secret(client: Client, path: str) -> None:
    assert _status(client, path, secret="wrong") == 403


@pytest.mark.parametrize("path", ["/api/v1/no-such-endpoint", "/_allauth/no-such-endpoint"])
def test_gated_paths_pass_through_with_the_right_secret(client: Client, path: str) -> None:
    # 404 comes from URL routing, so the request got past the middleware.
    assert _status(client, path, secret=SECRET) == 404


def test_secret_with_the_same_prefix_is_rejected(client: Client) -> None:
    assert _status(client, "/api/v1/teams", secret=SECRET[:-1]) == 403
    assert _status(client, "/api/v1/teams", secret=SECRET + "x") == 403


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/health/"])
def test_health_is_exempt(client: Client, path: str) -> None:
    assert _status(client, path) != 403


def test_stripe_webhooks_and_admin_are_not_gated(client: Client) -> None:
    assert _status(client, "/stripe/webhook/live", method="post") != 403
    assert _status(client, "/stripe/webhook/test", method="post") != 403
    assert _status(client, "/admin/login/") == 200


def test_paths_that_only_look_like_api_are_not_gated(client: Client) -> None:
    assert _status(client, "/apix/v1/teams") == 404
    assert _status(client, "/_allauthx/") == 404


def test_an_unset_secret_rejects_everything_gated(client: Client) -> None:
    with override_settings(PROXY_SECRET=""):
        assert _status(client, "/api/v1/teams", secret="") == 403
        assert _status(client, "/api/v1/teams") == 403


def test_non_ascii_secret_header_is_rejected_not_crashed(client: Client) -> None:
    assert _status(client, "/api/v1/teams", secret="sécret") == 403


def test_middleware_works_in_async_mode() -> None:
    async def get_response(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    middleware = proxy_secret_middleware(get_response)
    assert asyncio.iscoroutinefunction(middleware)
    factory = RequestFactory()

    async def call() -> tuple[int, int]:
        blocked = await middleware(factory.get("/api/v1/teams"))
        allowed = await middleware(
            factory.get("/api/v1/teams", headers={PROXY_SECRET_HEADER: SECRET})
        )
        return blocked.status_code, allowed.status_code

    assert asyncio.run(call()) == (403, 200)
