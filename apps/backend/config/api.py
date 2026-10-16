"""Shared pieces of the v1 API: the error body, the 501 stub response and the error handler."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import serializers, status
from rest_framework.exceptions import (
    APIException,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ErrorSerializer(serializers.Serializer[dict[str, str]]):
    """Every non-2xx JSON body: a stable machine code plus a message for people."""

    code = serializers.CharField()
    message = serializers.CharField()


class ModelUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "model_unavailable"
    default_detail = "No fitted model is available yet."


# DRF's own codes mapped onto the ones the API contract names.
_CODE_OVERRIDES = {"invalid": "validation_error", "throttled": "rate_limited"}


def not_implemented() -> Response:
    return Response(
        {"code": "not_implemented", "message": "This endpoint is not implemented yet."},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


def _flatten(detail: Any, prefix: str = "") -> list[str]:
    if isinstance(detail, dict):
        parts: list[str] = []
        for key, value in detail.items():
            parts.extend(_flatten(value, f"{prefix}{key}: " if key != "non_field_errors" else ""))
        return parts
    if isinstance(detail, list):
        parts = []
        for item in detail:
            parts.extend(_flatten(item, prefix))
        return parts
    return [f"{prefix}{detail}"]


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF's handler with the body rewritten to the contract's `{code, message}`."""
    if isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None or not isinstance(exc, APIException):
        return response

    code = str(exc.default_code)
    message = str(exc.detail)
    if isinstance(exc, ValidationError):
        message = "; ".join(_flatten(exc.detail))
    if isinstance(exc, NotAuthenticated):
        # The session scheme sends no WWW-Authenticate header, so DRF downgrades this to 403.
        response.status_code = status.HTTP_401_UNAUTHORIZED

    response.data = {"code": _CODE_OVERRIDES.get(code, code), "message": message}
    return response
