"""POST /api/v1/demo/start: the throwaway account, its session and the start limits."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework.test import APIClient

from ops import demo
from ops.models import DemoStartCount

URL = "/api/v1/demo/start"
ALLAUTH_SESSION = "/_allauth/browser/v1/auth/session"

pytestmark = pytest.mark.django_db


def start(client: APIClient, ip: str | None = "203.0.113.7") -> Any:
    return client.post(URL, headers={"x-client-ip": ip} if ip else {})


def test_the_limits_are_the_documented_numbers() -> None:
    assert demo.DEMO_STARTS_PER_IP_PER_DAY == 3
    assert demo.DEMO_STARTS_PER_DAY == 25


def test_start_answers_201_with_the_me_payload_of_a_new_demo_user(
    api_client: APIClient, demo_world: None
) -> None:
    before = timezone.now()

    response = start(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body["plan"] == "demo"
    assert body["is_demo"] is True
    assert body["role"] == "user"
    assert body["name"] is None
    assert body["subscription"] is None
    assert body["usage"]["used"] == 0
    assert body["usage"]["limit"] == 10
    expires = datetime.fromisoformat(body["demo_expires_at"])
    assert before + timedelta(hours=24) <= expires <= timezone.now() + timedelta(hours=24)


def test_the_user_has_an_undeliverable_valid_email_and_no_way_to_sign_in_again(
    api_client: APIClient, demo_world: None
) -> None:
    body = start(api_client).json()

    user = User.objects.get(pk=body["id"])
    validate_email(user.email)
    assert user.email.endswith("@demo.bundespredict.invalid")
    assert not user.has_usable_password()
    assert user.get_full_name() == ""
    assert not EmailAddress.objects.filter(user=user).exists()
    assert user.profile.is_demo is True


def test_the_next_request_with_the_cookie_is_the_demo_user(
    api_client: APIClient, demo_world: None
) -> None:
    assert api_client.get("/api/v1/me").status_code == 401

    started = start(api_client).json()
    me = api_client.get("/api/v1/me")

    assert me.status_code == 200
    assert me.json() == started


def test_allauth_also_reports_the_demo_user_as_signed_in(
    api_client: APIClient, demo_world: None
) -> None:
    started = start(api_client).json()

    response = api_client.get(ALLAUTH_SESSION)

    assert response.status_code == 200
    assert response.json()["data"]["user"]["id"] == started["id"]


def test_the_session_cookie_lives_as_long_as_the_account(
    api_client: APIClient, demo_world: None
) -> None:
    response = start(api_client)

    assert response.cookies[settings.SESSION_COOKIE_NAME]["max-age"] == 24 * 3600


def test_a_fourth_start_from_one_address_is_refused(
    api_client: APIClient, demo_world: None
) -> None:
    for _ in range(3):
        assert start(api_client).status_code == 201

    response = start(APIClient(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET))

    assert response.status_code == 429
    assert response.json()["code"] == "demo_ip_limit"
    assert response.json()["message"]
    assert User.objects.filter(profile__is_demo=True).count() == 3


def test_another_address_is_not_affected(api_client: APIClient, demo_world: None) -> None:
    for _ in range(3):
        start(api_client, ip="203.0.113.7")

    assert start(api_client, ip="203.0.113.8").status_code == 201


def test_the_site_wide_budget_runs_out(
    api_client: APIClient, demo_world: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(demo, "DEMO_STARTS_PER_DAY", 2)
    assert start(api_client, ip="203.0.113.1").status_code == 201
    assert start(api_client, ip="203.0.113.2").status_code == 201

    response = start(api_client, ip="203.0.113.3")

    assert response.status_code == 429
    assert response.json()["code"] == "demo_budget"


def test_an_ip_refusal_does_not_spend_the_site_budget(
    api_client: APIClient, demo_world: None
) -> None:
    for _ in range(3):
        start(api_client)
    start(api_client)

    site = DemoStartCount.objects.get(scope=demo.SITE_SCOPE)
    assert site.starts == 3


def test_a_start_that_fails_midway_spends_nothing(
    api_client: APIClient, demo_world: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("seeding broke")

    monkeypatch.setattr(demo, "seed_conversations", explode)
    api_client.raise_request_exception = False

    response = start(api_client)

    assert response.status_code == 500
    assert not DemoStartCount.objects.exists()
    assert not User.objects.filter(profile__is_demo=True).exists()


def test_only_a_keyed_hash_of_the_address_is_stored(
    api_client: APIClient, demo_world: None
) -> None:
    start(api_client, ip="203.0.113.7")

    scopes = set(DemoStartCount.objects.values_list("scope", flat=True))
    digest = hmac.new(settings.SECRET_KEY.encode(), b"demo-ip:203.0.113.7", sha256).hexdigest()
    assert scopes == {demo.SITE_SCOPE, f"ip:{digest}"}


def test_a_request_without_an_address_only_counts_against_the_site_budget(
    api_client: APIClient, demo_world: None
) -> None:
    statuses = [start(api_client, ip=None).status_code for _ in range(5)]

    assert statuses == [201] * 5
    assert list(DemoStartCount.objects.values_list("scope", flat=True)) == [demo.SITE_SCOPE]


def test_the_proxy_marker_for_an_unknown_address_is_treated_as_no_address(
    api_client: APIClient, demo_world: None
) -> None:
    statuses = [start(api_client, ip="unknown").status_code for _ in range(4)]

    assert statuses == [201] * 4


def test_counters_are_per_utc_day(demo_world: None) -> None:
    evening = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
    for _ in range(3):
        demo.start_demo(client_ip="203.0.113.7", now=evening)
    with pytest.raises(demo.DemoLimitReached):
        demo.start_demo(client_ip="203.0.113.7", now=evening)

    morning = evening + timedelta(hours=1)
    user = demo.start_demo(client_ip="203.0.113.7", now=morning)

    assert user.profile.demo_expires_at == morning + timedelta(hours=24)
