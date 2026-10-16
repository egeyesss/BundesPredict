"""Email-code sign-in and the Google redirect, walked through allauth's headless browser API."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client
from django.urls import resolve, reverse

AUTH = "/_allauth/browser/v1/auth"
CODE_LINE = re.compile(r"^\s*([A-Z0-9]{4}-[A-Z0-9]{4})\s*$", re.MULTILINE)

pytestmark = pytest.mark.django_db


@pytest.fixture
def browser() -> Client:
    return Client(headers={"x-proxy-secret": settings.PROXY_SECRET})


def _registered_user(username: str, email: str) -> User:
    user = User.objects.create_user(username=username, email=email)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def _post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(f"{AUTH}/{path}", body, content_type="application/json")


def _emailed_code() -> str:
    match = CODE_LINE.search(str(mail.outbox[-1].body))
    assert match, mail.outbox[-1].body
    return match.group(1)


def _flow_ids(response: Any) -> set[str]:
    return {flow["id"] for flow in response.json()["data"]["flows"]}


def test_an_existing_user_signs_in_with_an_emailed_code(browser: Client) -> None:
    user = _registered_user("grace", "grace@example.com")

    requested = _post(browser, "code/request", {"email": "grace@example.com"})
    assert requested.status_code == 401
    assert "login_by_code" in _flow_ids(requested)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["grace@example.com"]

    confirmed = _post(browser, "code/confirm", {"code": _emailed_code()})
    assert confirmed.status_code == 200
    assert confirmed.json()["meta"]["is_authenticated"] is True

    me = browser.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["id"] == user.pk
    assert me.json()["email"] == "grace@example.com"
    assert me.json()["usage"]["used"] == 0


def test_a_new_email_signs_up_without_a_password_and_verifies_by_code(browser: Client) -> None:
    signup = _post(browser, "signup", {"email": "new@example.com"})
    assert signup.status_code == 401
    assert "verify_email" in _flow_ids(signup)

    verified = _post(browser, "email/verify", {"key": _emailed_code()})
    assert verified.status_code == 200

    user = User.objects.get(email="new@example.com")
    assert not user.has_usable_password()
    me = browser.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["id"] == user.pk
    assert user.profile.role == "user"


def test_a_wrong_code_does_not_sign_anyone_in(browser: Client) -> None:
    _registered_user("linus", "linus@example.com")
    _post(browser, "code/request", {"email": "linus@example.com"})

    wrong = _post(browser, "code/confirm", {"code": "AAAA-AAAA"})

    assert wrong.status_code == 400
    assert browser.get("/api/v1/me").status_code == 401


def test_an_unknown_email_gets_no_login_code(browser: Client) -> None:
    requested = _post(browser, "code/request", {"email": "ghost@example.com"})

    assert requested.status_code == 401
    assert not User.objects.filter(email="ghost@example.com").exists()
    assert CODE_LINE.search(str(mail.outbox[-1].body)) is None


def test_the_session_endpoint_requires_the_proxy_secret() -> None:
    bare = Client()

    assert bare.get(f"{AUTH}/session").status_code == 403
    assert bare.post(f"{AUTH}/code/request", {}, content_type="application/json").status_code == 403


def test_the_google_redirect_points_at_google_with_the_callback(
    browser: Client, settings: Any
) -> None:
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APPS": [{"client_id": "test-client-id.apps.googleusercontent.com", "secret": "s"}],
            "SCOPE": ["profile", "email"],
        }
    }

    response = browser.post(
        f"{AUTH}/provider/redirect",
        {"provider": "google", "callback_url": "/", "process": "login"},
    )

    assert response.status_code == 302
    target = urlparse(response["Location"])
    assert target.netloc == "accounts.google.com"
    query = parse_qs(target.query)
    assert query["client_id"] == ["test-client-id.apps.googleusercontent.com"]
    assert query["redirect_uri"] == ["http://testserver/accounts/google/login/callback/"]


def test_the_google_callback_resolves_to_allauths_view() -> None:
    assert reverse("google_callback") == "/accounts/google/login/callback/"
    assert resolve("/accounts/google/login/callback/").func.__module__.startswith(
        "allauth.socialaccount.providers.oauth2"
    )
