"""Stripe webhooks: signature check, idempotency and syncing from a re-fetched subscription."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from billing import stripe_api
from billing.models import StripeCustomer, StripeEvent, Subscription

TEST_URL = "/stripe/webhook/test"
LIVE_URL = "/stripe/webhook/live"
TEST_SECRET = "whsec_unit_test_secret"
LIVE_SECRET = "whsec_unit_live_secret"
PERIOD_END = datetime(2026, 11, 20, tzinfo=UTC)

pytestmark = pytest.mark.django_db


def _sign(payload: str, secret: str) -> str:
    timestamp = int(time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256)
    return f"t={timestamp},v1={digest.hexdigest()}"


def _event(event_id: str, event_type: str, obj: dict[str, Any], livemode: bool = False) -> str:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "livemode": livemode,
            "data": {"object": obj},
        }
    )


@pytest.fixture(autouse=True)
def webhook_secrets(settings: Any) -> None:
    settings.STRIPE_WEBHOOK_SECRET_TEST = TEST_SECRET
    settings.STRIPE_WEBHOOK_SECRET_LIVE = LIVE_SECRET


@pytest.fixture
def client() -> APIClient:
    return APIClient(raise_request_exception=False)


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="payer", email="payer@example.com")


@pytest.fixture
def customer(user: User) -> StripeCustomer:
    return StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_1")


@pytest.fixture
def stripe_state(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """What Stripe reports when the webhook re-fetches the subscription; tests edit it."""
    state: dict[str, Any] = {
        "status": "active",
        "cancel_at_period_end": False,
        "calls": [],
    }

    def fetch(livemode: bool, subscription_id: str) -> stripe_api.SubscriptionSnapshot:
        state["calls"].append((livemode, subscription_id))
        return stripe_api.SubscriptionSnapshot(
            id=subscription_id,
            customer_id="cus_1",
            status=state["status"],
            current_period_end=PERIOD_END,
            cancel_at_period_end=state["cancel_at_period_end"],
        )

    monkeypatch.setattr(stripe_api, "fetch_subscription", fetch)
    return state


@pytest.fixture
def post(client: APIClient) -> Callable[..., Any]:
    def send(payload: str, secret: str = TEST_SECRET, url: str = TEST_URL) -> Any:
        return client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=_sign(payload, secret),
        )

    return send


def _subscription_event(event_id: str, event_type: str, status: str = "incomplete") -> str:
    return _event(event_id, event_type, {"id": "sub_1", "object": "subscription", "status": status})


def test_a_bad_signature_is_rejected_and_stores_nothing(
    client: APIClient, customer: StripeCustomer, stripe_state: dict[str, Any]
) -> None:
    payload = _subscription_event("evt_1", "customer.subscription.created")

    response = client.post(
        TEST_URL,
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=_sign(payload, "whsec_wrong"),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_signature"
    assert not StripeEvent.objects.exists()
    assert stripe_state["calls"] == []


def test_a_missing_signature_header_is_rejected(client: APIClient) -> None:
    response = client.post(TEST_URL, data="{}", content_type="application/json")

    assert response.status_code == 400


def test_an_unconfigured_secret_rejects_even_a_payload_signed_with_an_empty_key(
    client: APIClient, settings: Any
) -> None:
    settings.STRIPE_WEBHOOK_SECRET_TEST = ""
    payload = _subscription_event("evt_1", "customer.subscription.created")

    response = client.post(
        TEST_URL,
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=_sign(payload, ""),
    )

    assert response.status_code == 400


def test_each_endpoint_only_trusts_its_own_secret(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    payload = _subscription_event("evt_1", "customer.subscription.created")

    assert post(payload, secret=LIVE_SECRET, url=TEST_URL).status_code == 400
    assert post(payload, secret=TEST_SECRET, url=LIVE_URL).status_code == 400
    assert not Subscription.objects.exists()


def test_the_same_event_twice_is_processed_once(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    payload = _subscription_event("evt_1", "customer.subscription.created")

    assert post(payload).status_code == 200
    assert post(payload).status_code == 200

    assert stripe_state["calls"] == [(False, "sub_1")]
    assert StripeEvent.objects.filter(event_id="evt_1").count() == 1
    assert Subscription.objects.count() == 1


def test_updated_arriving_before_created_ends_in_the_current_state(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    stripe_state.update(status="active", cancel_at_period_end=True)

    post(_subscription_event("evt_2", "customer.subscription.updated", status="active"))
    post(_subscription_event("evt_1", "customer.subscription.created", status="incomplete"))

    subscription = Subscription.objects.get()
    assert subscription.status == "active"
    assert subscription.cancel_at_period_end is True
    assert subscription.current_period_end == PERIOD_END
    assert subscription.customer == customer


def test_a_later_event_overwrites_the_row_with_the_refetched_state(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    post(_subscription_event("evt_1", "customer.subscription.created"))
    stripe_state.update(status="canceled")

    post(_subscription_event("evt_2", "customer.subscription.deleted"))

    assert Subscription.objects.get().status == "canceled"


def test_checkout_completed_creates_the_customer_from_client_reference_id(
    user: User, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    session = {
        "id": "cs_1",
        "object": "checkout.session",
        "client_reference_id": str(user.pk),
        "customer": "cus_1",
        "subscription": "sub_1",
    }

    assert post(_event("evt_1", "checkout.session.completed", session)).status_code == 200

    assert StripeCustomer.objects.get().user == user
    assert Subscription.objects.get().subscription_id == "sub_1"


def test_invoice_events_sync_the_subscription_named_in_the_invoice_parent(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    stripe_state.update(status="past_due")
    invoice = {
        "id": "in_1",
        "object": "invoice",
        "parent": {"subscription_details": {"subscription": "sub_1"}},
    }

    assert post(_event("evt_1", "invoice.payment_failed", invoice)).status_code == 200

    assert Subscription.objects.get().status == "past_due"


def test_invoice_paid_with_the_legacy_subscription_field_still_syncs(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    invoice = {"id": "in_1", "object": "invoice", "subscription": "sub_1"}

    post(_event("evt_1", "invoice.paid", invoice))

    assert Subscription.objects.get().status == "active"


def test_an_invoice_without_a_subscription_is_accepted_and_ignored(
    customer: StripeCustomer, stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    invoice = {"id": "in_1", "object": "invoice"}

    assert post(_event("evt_1", "invoice.paid", invoice)).status_code == 200
    assert not Subscription.objects.exists()


def test_a_subscription_for_an_unknown_customer_is_acknowledged_without_a_row(
    stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    assert post(_subscription_event("evt_1", "customer.subscription.created")).status_code == 200

    assert not Subscription.objects.exists()


def test_an_unhandled_event_type_is_acknowledged(
    stripe_state: dict[str, Any], post: Callable[..., Any]
) -> None:
    payload = _event("evt_1", "charge.succeeded", {"id": "ch_1", "object": "charge"})

    assert post(payload).status_code == 200
    assert stripe_state["calls"] == []


def test_a_failure_while_syncing_leaves_no_event_row_so_stripe_can_retry(
    customer: StripeCustomer,
    stripe_state: dict[str, Any],
    post: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(livemode: bool, subscription_id: str) -> stripe_api.SubscriptionSnapshot:
        raise RuntimeError("stripe is down")

    monkeypatch.setattr(stripe_api, "fetch_subscription", broken)
    payload = _subscription_event("evt_1", "customer.subscription.created")

    assert post(payload).status_code == 500
    assert not StripeEvent.objects.exists()

    monkeypatch.undo()
    monkeypatch.setattr(
        stripe_api,
        "fetch_subscription",
        lambda livemode, subscription_id: stripe_api.SubscriptionSnapshot(
            subscription_id, "cus_1", "active", PERIOD_END, False
        ),
    )
    assert post(payload).status_code == 200
    assert Subscription.objects.get().status == "active"
