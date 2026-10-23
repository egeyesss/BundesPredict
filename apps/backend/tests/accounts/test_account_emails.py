"""What the allauth emails say, whichever host the request came through."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.test import Client

AUTH = "/_allauth/browser/v1/auth"
STRANGE_HOST = "localhost:3500"
SITE = "https://app.bundespredict.test"
CODE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b")
FORBIDDEN = ["Hello from", "Thank you for using", "password", "localhost", "example.com"]

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _public_site(settings: Any) -> None:
    settings.PUBLIC_SITE_URL = SITE
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, STRANGE_HOST.split(":")[0]]


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def browser() -> Client:
    return Client(headers={"x-proxy-secret": settings.PROXY_SECRET}, HTTP_HOST=STRANGE_HOST)


def _post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(f"{AUTH}/{path}", body, content_type="application/json")


def _registered(email: str) -> None:
    user = User.objects.create_user(username=email, email=email)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)


def _sent() -> tuple[str, str, str]:
    """Subject, plain body and HTML body of the last mail."""
    message = mail.outbox[-1]
    assert isinstance(message, EmailMultiAlternatives)
    html = [content for content, mimetype in message.alternatives if mimetype == "text/html"]
    assert len(html) == 1, "the mail must carry an HTML alternative"
    return str(message.subject), str(message.body), str(html[0])


def _visible_text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", html).split())


def _assert_own_wording(subject: str, text: str, html: str) -> None:
    for part in (subject, text, html):
        assert "BundesPredict" in part
        for phrase in FORBIDDEN:
            assert phrase.lower() not in part.lower(), (phrase, part)
    assert SITE in text
    assert " ".join(text.split()) == _visible_text(html)
    assert set(re.findall(r'href="([^"]+)"', html)) <= {SITE, f"{SITE}/login"}


def test_the_login_code_email_is_ours_and_carries_the_code(browser: Client) -> None:
    _registered("grace@example.com")

    _post(browser, "code/request", {"email": "grace@example.com"})

    subject, text, html = _sent()
    assert subject == "Your BundesPredict sign-in code"
    code = CODE.search(text)
    assert code and code.group(0) in html
    assert "expires" in text
    _assert_own_wording(subject, text, html)


def test_the_signup_verification_email_is_ours_and_carries_the_code(browser: Client) -> None:
    _post(browser, "signup", {"email": "new@example.com"})

    subject, text, html = _sent()
    assert subject == "Your BundesPredict verification code"
    code = CODE.search(text)
    assert code and code.group(0) in html
    _assert_own_wording(subject, text, html)


def test_the_unknown_account_email_is_ours(browser: Client) -> None:
    _post(browser, "code/request", {"email": "ghost@example.com"})

    _assert_own_wording(*_sent())


def test_the_account_already_exists_email_points_to_login_without_passwords(
    browser: Client,
) -> None:
    _registered("taken@example.com")

    _post(browser, "signup", {"email": "taken@example.com"})

    subject, text, html = _sent()
    _assert_own_wording(subject, text, html)
    assert f"{SITE}/login" in text
    assert "Google" in text
    assert "code" in text
