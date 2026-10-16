from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import stripe
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import plans
from config.api import ErrorSerializer

from . import stripe_api, sync
from .models import StripeCustomer
from .serializers import BillingRedirectSerializer

F = TypeVar("F", bound=Callable[..., Any])


class NoBillingAccount(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "no_billing_account"
    default_detail = "This account has no billing history yet."


class InvalidSignature(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_signature"
    default_detail = "The Stripe signature did not verify."


def _return_url(path: str) -> str:
    return f"{settings.STRIPE_RETURN_BASE_URL.rstrip('/')}{path}"


def _customer_id_for(user: User, livemode: bool) -> str:
    customer = StripeCustomer.objects.filter(user=user, livemode=livemode).first()
    if customer is not None:
        return customer.customer_id
    customer_id = stripe_api.create_customer(livemode=livemode, user_id=user.pk, email=user.email)
    customer, _ = StripeCustomer.objects.get_or_create(
        user=user, livemode=livemode, defaults={"customer_id": customer_id}
    )
    return customer.customer_id


class CheckoutView(APIView):
    @extend_schema(
        operation_id="billing_checkout",
        tags=["billing"],
        request=None,
        responses={200: BillingRedirectSerializer, 401: ErrorSerializer},
        description="Starts a Stripe Checkout session for the Pro plan.",
    )
    def post(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        livemode = stripe_api.livemode_for(user)
        customer_id = _customer_id_for(user, livemode)
        if plans.has_pro(user):
            # A second subscription would bill twice; manage the existing one instead.
            url = stripe_api.create_portal_url(
                livemode=livemode, customer_id=customer_id, return_url=_return_url("/account")
            )
        else:
            url = stripe_api.create_checkout_url(
                livemode=livemode,
                customer_id=customer_id,
                price_id=stripe_api.price_id(livemode),
                client_reference_id=str(user.pk),
                success_url=_return_url("/account?checkout=success"),
                cancel_url=_return_url("/account"),
            )
        return Response({"url": url})


class PortalView(APIView):
    @extend_schema(
        operation_id="billing_portal",
        tags=["billing"],
        request=None,
        responses={200: BillingRedirectSerializer, 401: ErrorSerializer},
        description="Opens the Stripe Customer Portal for the signed-in user.",
    )
    def post(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        livemode = stripe_api.livemode_for(user)
        customer = StripeCustomer.objects.filter(user=user, livemode=livemode).first()
        if customer is None:
            raise NoBillingAccount
        url = stripe_api.create_portal_url(
            livemode=livemode, customer_id=customer.customer_id, return_url=_return_url("/account")
        )
        return Response({"url": url})


def _handle_webhook(request: HttpRequest, livemode: bool) -> Response:
    secret = (
        settings.STRIPE_WEBHOOK_SECRET_LIVE if livemode else settings.STRIPE_WEBHOOK_SECRET_TEST
    )
    signature = request.headers.get("Stripe-Signature", "")
    if not secret or not signature:
        raise InvalidSignature
    try:
        event = stripe_api.construct_event(request.body, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as error:
        raise InvalidSignature from error
    sync.handle_event(event, livemode)
    return Response(status=status.HTTP_200_OK)


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
        return _handle_webhook(request, livemode=True)


class StripeTestWebhookView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @_webhook_schema("stripe_webhook_test")
    def post(self, request: Request) -> Response:
        return _handle_webhook(request, livemode=False)
