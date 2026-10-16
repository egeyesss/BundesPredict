from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest
import sentry_sdk

LoadProd = Callable[..., ModuleType]

PROD_ENV = {
    "DJANGO_SECRET_KEY": "not-a-real-key",
    "DJANGO_ALLOWED_HOSTS": "backend.example.com",
    "PROXY_SECRET": "not-a-real-secret",
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
}


@pytest.fixture
def load_prod(monkeypatch: pytest.MonkeyPatch) -> LoadProd:
    """Imports `config.settings.prod` fresh, with a clean environment plus `extra`."""

    def load(**extra: str) -> ModuleType:
        for name in ("SENTRY_DSN_BACKEND", "DJANGO_CSRF_TRUSTED_ORIGINS", "DJANGO_SETTINGS_MODULE"):
            monkeypatch.delenv(name, raising=False)
        for name, value in {**PROD_ENV, **extra}.items():
            monkeypatch.setenv(name, value)
        for module in ("config.settings.prod", "config.settings.base"):
            sys.modules.pop(module, None)
        return importlib.import_module("config.settings.prod")

    return load


def test_the_forwarded_host_is_trusted_so_allauth_builds_the_public_redirect_uri(
    load_prod: LoadProd,
) -> None:
    settings = load_prod()

    assert settings.USE_X_FORWARDED_HOST is True
    assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_the_public_origin_is_a_csrf_trusted_origin_by_default(load_prod: LoadProd) -> None:
    assert load_prod().CSRF_TRUSTED_ORIGINS == ["https://bundespredict.egeyesilyurt.ca"]


def test_trusted_origins_can_be_overridden_from_the_environment(load_prod: LoadProd) -> None:
    settings = load_prod(DJANGO_CSRF_TRUSTED_ORIGINS="https://a.example.com,https://b.example.com")

    assert settings.CSRF_TRUSTED_ORIGINS == ["https://a.example.com", "https://b.example.com"]


def test_cookies_are_secure_and_lax_for_same_origin_use_through_the_proxy(
    load_prod: LoadProd,
) -> None:
    settings = load_prod()

    assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_COOKIE_HTTPONLY is True
    # The web app reads the csrftoken cookie to send X-CSRFToken.
    assert settings.CSRF_COOKIE_HTTPONLY is False


def test_whitenoise_serves_admin_static_files_right_after_the_security_middleware(
    load_prod: LoadProd,
) -> None:
    settings = load_prod()
    middleware = settings.MIDDLEWARE

    assert middleware[0] == "config.middleware.proxy_secret_middleware"
    position = middleware.index("django.middleware.security.SecurityMiddleware")
    assert middleware[position + 1] == "whitenoise.middleware.WhiteNoiseMiddleware"
    assert settings.STATIC_ROOT.name == "staticfiles"
    assert (
        settings.STORAGES["staticfiles"]["BACKEND"]
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


def test_sentry_stays_off_without_a_dsn(
    load_prod: LoadProd, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    load_prod()

    assert calls == []


def test_sentry_starts_with_the_dsn_and_scrubs_the_proxy_headers(
    load_prod: LoadProd, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    load_prod(SENTRY_DSN_BACKEND="https://key@o1.ingest.sentry.io/2")

    (kwargs,) = calls
    assert kwargs["dsn"] == "https://key@o1.ingest.sentry.io/2"
    assert kwargs["send_default_pii"] is False
    denylist = kwargs["event_scrubber"].denylist
    assert {"x-proxy-secret", "x_proxy_secret", "x-client-ip"} <= set(denylist)
