from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer, not_implemented

from .serializers import BillingRedirectSerializer

F = TypeVar("F", bound=Callable[..., Any])


class CheckoutView(APIView):
    @extend_schema(
        operation_id="billing_checkout",
        tags=["billing"],
        request=None,
        responses={200: BillingRedirectSerializer, 401: ErrorSerializer},
        description="Starts a Stripe Checkout session for the Pro plan.",
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


class PortalView(APIView):
    @extend_schema(
        operation_id="billing_portal",
        tags=["billing"],
        request=None,
        responses={200: BillingRedirectSerializer, 401: ErrorSerializer},
        description="Opens the Stripe Customer Portal for the signed-in user.",
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


def _webhook_schema(operation_id: str) -> Callable[[F], F]:
    return extend_schema(
        operation_id=operation_id,
        tags=["billing"],
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiResponse(description="Event accepted."), 400: ErrorSerializer},
        description="Signed with the `Stripe-Signature` header; called by Stripe, not the proxy.",
    )


class StripeLiveWebhookView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @_webhook_schema("stripe_webhook_live")
    def post(self, request: Request) -> Response:
        return not_implemented()


class StripeTestWebhookView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @_webhook_schema("stripe_webhook_test")
    def post(self, request: Request) -> Response:
        return not_implemented()
