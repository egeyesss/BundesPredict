"""Rejects API traffic that did not come through the Next.js proxy."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import sync_and_async_middleware

PROXY_SECRET_HEADER = "x-proxy-secret"

GATED_PREFIXES = ("/api/", "/_allauth/")
EXEMPT_PATHS = ("/api/v1/health", "/api/v1/health/")


def _is_gated(path: str) -> bool:
    return path.startswith(GATED_PREFIXES) and path not in EXEMPT_PATHS


def _has_valid_secret(request: HttpRequest) -> bool:
    expected = settings.PROXY_SECRET
    if not expected:
        return False
    supplied = request.headers.get(PROXY_SECRET_HEADER, "")
    return hmac.compare_digest(supplied.encode(), expected.encode())


def _forbidden() -> HttpResponse:
    return JsonResponse(
        {"code": "forbidden", "message": "Requests must come through the web proxy."},
        status=403,
    )


@sync_and_async_middleware
def proxy_secret_middleware(get_response: Callable[..., Any]) -> Callable[..., Any]:
    """403 on `/api/*` and `/_allauth/*` without the shared secret, except the health check.

    Stripe webhooks and the Django admin live on other paths and are not gated here. Written as a
    hybrid so the async SSE view is not pushed through a sync-to-async adapter.
    """
    if iscoroutinefunction(get_response):

        async def async_middleware(request: HttpRequest) -> HttpResponse:
            if _is_gated(request.path_info) and not _has_valid_secret(request):
                return _forbidden()
            response: HttpResponse = await get_response(request)
            return response

        return async_middleware

    def sync_middleware(request: HttpRequest) -> HttpResponse:
        if _is_gated(request.path_info) and not _has_valid_secret(request):
            return _forbidden()
        response: HttpResponse = get_response(request)
        return response

    return sync_middleware
