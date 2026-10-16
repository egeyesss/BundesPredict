"""The only module that talks to Stripe; everything else calls these functions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

import stripe
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser


@dataclass(frozen=True)
class SubscriptionSnapshot:
    id: str
    customer_id: str
    status: str
    current_period_end: datetime
    cancel_at_period_end: bool


def livemode_for(user: AbstractBaseUser) -> bool:
    """Demo users always bill in test mode; real users go live once a live key is configured."""
    if getattr(getattr(user, "profile", None), "is_demo", False):
        return False
    return bool(settings.STRIPE_SECRET_KEY_LIVE)


def price_id(livemode: bool) -> str:
    return str(settings.STRIPE_PRICE_ID_LIVE if livemode else settings.STRIPE_PRICE_ID_TEST)


def _client(livemode: bool) -> stripe.StripeClient:
    key = settings.STRIPE_SECRET_KEY_LIVE if livemode else settings.STRIPE_SECRET_KEY_TEST
    return stripe.StripeClient(key)


def fetch_subscription(livemode: bool, subscription_id: str) -> SubscriptionSnapshot:
    subscription = _client(livemode).v1.subscriptions.retrieve(subscription_id)
    # The period lives on the items since the 2025 API versions; one price means one item.
    period_end = subscription["items"]["data"][0]["current_period_end"]
    return SubscriptionSnapshot(
        id=subscription.id,
        customer_id=_id_of(subscription["customer"]),
        status=subscription.status,
        current_period_end=datetime.fromtimestamp(period_end, tz=UTC),
        cancel_at_period_end=bool(subscription.cancel_at_period_end),
    )


def _id_of(customer: str | stripe.Customer) -> str:
    return customer if isinstance(customer, str) else customer.id


def create_customer(*, livemode: bool, user_id: int, email: str) -> str:
    customer = _client(livemode).v1.customers.create(
        {"email": email, "metadata": {"user_id": str(user_id)}},
        {"idempotency_key": f"customer-{int(livemode)}-{user_id}"},
    )
    return customer.id


def create_checkout_url(
    *,
    livemode: bool,
    customer_id: str,
    price_id: str,
    client_reference_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    session = _client(livemode).v1.checkout.sessions.create(
        {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": client_reference_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
    )
    assert session.url is not None
    return session.url


def create_portal_url(*, livemode: bool, customer_id: str, return_url: str) -> str:
    session = _client(livemode).v1.billing_portal.sessions.create(
        {"customer": customer_id, "return_url": return_url}
    )
    return session.url


def construct_event(payload: bytes, signature: str, secret: str) -> stripe.Event:
    event: stripe.Event = stripe.Webhook.construct_event(payload, signature, secret)
    return event


def clock_create(frozen_time: datetime) -> str:
    clock = _client(False).v1.test_helpers.test_clocks.create(
        {"frozen_time": int(frozen_time.timestamp())}
    )
    return clock.id


def clock_add_subscriber(*, clock_id: str, email: str, payment_method: str) -> tuple[str, str]:
    client = _client(False)
    customer = client.v1.customers.create({"email": email, "test_clock": clock_id})
    client.v1.payment_methods.attach(payment_method, {"customer": customer.id})
    client.v1.customers.update(
        customer.id, {"invoice_settings": {"default_payment_method": payment_method}}
    )
    subscription = client.v1.subscriptions.create(
        {"customer": customer.id, "items": [{"price": price_id(False)}]}
    )
    return customer.id, subscription.id


def clock_set_payment_method(customer_id: str, payment_method: str) -> None:
    client = _client(False)
    client.v1.payment_methods.attach(payment_method, {"customer": customer_id})
    client.v1.customers.update(
        customer_id, {"invoice_settings": {"default_payment_method": payment_method}}
    )


def clock_advance(clock_id: str, frozen_time: datetime, timeout_seconds: int = 120) -> None:
    clocks = _client(False).v1.test_helpers.test_clocks
    clocks.advance(clock_id, {"frozen_time": int(frozen_time.timestamp())})
    deadline = time.monotonic() + timeout_seconds
    while clocks.retrieve(clock_id).status != "ready":
        if time.monotonic() > deadline:
            raise TimeoutError(f"test clock {clock_id} did not finish advancing")
        time.sleep(2)


def clock_delete(clock_id: str) -> None:
    _client(False).v1.test_helpers.test_clocks.delete(clock_id)
