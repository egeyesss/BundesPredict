"""GET and PATCH /api/v1/me against real users and profiles."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts import quota
from accounts.models import UserProfile

ME = "/api/v1/me"

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        username="ada", email="ada@example.com", first_name="Ada", last_name="Lovelace"
    )


@pytest.fixture
def client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def test_me_requires_a_session(api_client: APIClient) -> None:
    for response in (api_client.get(ME), api_client.patch(ME, {}, format="json")):
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"


def test_new_users_get_a_profile(user: User) -> None:
    profile = UserProfile.objects.get(user=user)

    assert (profile.role, profile.is_demo, profile.email_opt_in) == ("user", False, True)
    assert (profile.timezone, profile.timezone_source) == (None, "browser")


def test_get_returns_the_contract_shape(client: APIClient, user: User) -> None:
    body = client.get(ME).json()

    assert set(body) == {
        "id",
        "email",
        "name",
        "plan",
        "role",
        "is_demo",
        "usage",
        "subscription",
        "email_opt_in",
        "timezone",
    }
    assert body["id"] == user.pk
    assert body["email"] == "ada@example.com"
    assert body["name"] == "Ada Lovelace"
    assert (body["plan"], body["role"], body["is_demo"]) == ("free", "user", False)
    assert body["subscription"] is None
    assert body["email_opt_in"] is True
    assert body["timezone"] is None
    assert body["usage"]["used"] == 0
    assert body["usage"]["limit"] == 3
    assert body["usage"]["resets_at"].endswith("T00:00:00Z")


def test_name_is_null_when_the_user_has_none(api_client: APIClient) -> None:
    nameless = User.objects.create_user(username="n", email="n@example.com")
    api_client.force_authenticate(user=nameless)

    assert api_client.get(ME).json()["name"] is None


def test_get_reports_chats_already_used(client: APIClient, user: User) -> None:
    quota.consume(user)
    quota.consume(user)

    assert client.get(ME).json()["usage"]["used"] == 2


def test_get_creates_a_missing_profile(client: APIClient, user: User) -> None:
    UserProfile.objects.filter(user=user).delete()

    assert client.get(ME).status_code == 200
    assert UserProfile.objects.filter(user=user).exists()


def test_a_demo_profile_reports_the_demo_plan(client: APIClient, user: User) -> None:
    UserProfile.objects.filter(user=user).update(is_demo=True)

    body = client.get(ME).json()

    assert (body["plan"], body["is_demo"]) == ("demo", True)


def test_patch_updates_email_opt_in(client: APIClient, user: User) -> None:
    body = client.patch(ME, {"email_opt_in": False}, format="json").json()

    assert body["email_opt_in"] is False
    assert UserProfile.objects.get(user=user).email_opt_in is False


def test_patch_ignores_fields_that_are_not_writable(client: APIClient, user: User) -> None:
    client.patch(ME, {"role": "admin", "is_demo": True, "plan": "pro"}, format="json")

    profile = UserProfile.objects.get(user=user)
    assert (profile.role, profile.is_demo) == ("user", False)


def _timezone_state(user: User) -> tuple[str | None, str]:
    profile = UserProfile.objects.get(user=user)
    return profile.timezone, profile.timezone_source


def test_the_browser_timezone_is_stored(client: APIClient, user: User) -> None:
    response = client.patch(ME, {"timezone": "America/Toronto"}, format="json")

    assert response.json()["timezone"] == "America/Toronto"
    assert _timezone_state(user) == ("America/Toronto", "browser")


def test_the_browser_timezone_follows_the_user_while_it_is_not_manual(
    client: APIClient, user: User
) -> None:
    client.patch(ME, {"timezone": "America/Toronto"}, format="json")
    client.patch(ME, {"timezone": "Europe/Istanbul"}, format="json")

    assert _timezone_state(user) == ("Europe/Istanbul", "browser")


def test_a_manual_timezone_wins_over_later_browser_reports(client: APIClient, user: User) -> None:
    client.patch(ME, {"timezone": "Asia/Tokyo", "timezone_source": "manual"}, format="json")

    response = client.patch(ME, {"timezone": "America/Toronto"}, format="json")

    assert response.status_code == 200
    assert response.json()["timezone"] == "Asia/Tokyo"
    assert _timezone_state(user) == ("Asia/Tokyo", "manual")


def test_a_manual_timezone_can_be_replaced_by_another_manual_one(
    client: APIClient, user: User
) -> None:
    client.patch(ME, {"timezone": "Asia/Tokyo", "timezone_source": "manual"}, format="json")
    client.patch(ME, {"timezone": "Europe/Berlin", "timezone_source": "manual"}, format="json")

    assert _timezone_state(user) == ("Europe/Berlin", "manual")


def test_clearing_the_timezone_hands_control_back_to_the_browser(
    client: APIClient, user: User
) -> None:
    client.patch(ME, {"timezone": "Asia/Tokyo", "timezone_source": "manual"}, format="json")

    client.patch(ME, {"timezone": None, "timezone_source": "manual"}, format="json")
    assert _timezone_state(user) == (None, "browser")

    client.patch(ME, {"timezone": "America/Toronto"}, format="json")
    assert _timezone_state(user) == ("America/Toronto", "browser")


@pytest.mark.parametrize("payload", [{"timezone": "Mars/Olympus"}, {"timezone": ""}])
def test_an_unknown_timezone_is_a_validation_error(
    client: APIClient, user: User, payload: dict[str, Any]
) -> None:
    response = client.patch(ME, payload, format="json")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"].startswith("timezone:")
    assert _timezone_state(user) == (None, "browser")


def test_an_unknown_timezone_source_is_a_validation_error(client: APIClient) -> None:
    response = client.patch(ME, {"timezone_source": "cosmic"}, format="json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("timezone_source:")
