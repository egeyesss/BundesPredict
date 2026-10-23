"""Account adapter that names the product and public site in every allauth email."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

PRODUCT_NAME = "BundesPredict"


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]
    """Fixes the site name and URL, which allauth otherwise takes from the request host."""

    def format_email_subject(self, subject: str) -> str:
        return subject

    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        site_url = settings.PUBLIC_SITE_URL.rstrip("/")
        site = SimpleNamespace(name=PRODUCT_NAME, domain=urlparse(site_url).netloc)
        super().send_mail(
            template_prefix, email, {**context, "current_site": site, "site_url": site_url}
        )
