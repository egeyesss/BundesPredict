from __future__ import annotations

import importlib

import pytest
from django.apps import apps
from django.urls import URLResolver

from config import urls as root_urls

APP_NAMES = [
    "football",
    "predictions",
    "accounts",
    "chat",
    "billing",
    "track_record",
    "notifications",
    "ops",
]


@pytest.mark.parametrize("app_name", APP_NAMES)
def test_app_is_installed(app_name: str) -> None:
    assert apps.is_installed(app_name)


URL_MODULES = [f"{app_name}.urls" for app_name in APP_NAMES] + [
    "accounts.auth_urls",
    "billing.webhook_urls",
]


@pytest.mark.parametrize("module_name", URL_MODULES)
def test_urlconf_is_included_in_the_root_urlconf(module_name: str) -> None:
    app_urls = importlib.import_module(module_name)

    included = [
        pattern.urlconf_name
        for pattern in root_urls.urlpatterns
        if isinstance(pattern, URLResolver)
    ]

    assert app_urls in included
