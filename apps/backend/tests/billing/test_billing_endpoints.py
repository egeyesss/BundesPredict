"""POST /billing/checkout and /billing/portal, plus the subscription block on /me."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from billing import stripe_api
from billing.models import StripeCustomer, Subscription

CHECKOUT = "/api/v1/billing/checkout"
PORTAL = "/api/v1/billing/portal"
ME = "/api/v1/me"

pytestmark = pytest.mark.django_db


class FakeStripe:
    def __init__(self) -> None:
        self.customers_created: list[dict[str, Any]] = []
        self.checkouts: list[dict[str, Any]] = []
        self.portals: list[dict[str, Any]] = []

    def create_customer(self, *, livemode: bool, user_id: int, email: str) -> str:
        self.customers_created.append({"livemode": livemode, "user_id": user_id, "email": email})
        return f"cus_new_{len(self.customers_created)}"

    def create_checkout_url(self, **kwargs: Any) -> str:
        self.checkouts.append(kwargs)
        return "https://checkout.stripe.test/c/pay"

    def create_portal_url(self, **kwargs: Any) -> str:
        self.portals.append(kwargs)
        return "https://billing.stripe.test/p/session"


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch, settings: Any) -> FakeStripe:
    settings.STRIPE_SECRET_KEY_LIVE = ""
    settings.STRIPE_PRICE_ID_TEST = "price_test_unit"
    settings.STRIPE_RETURN_BASE_URL = "https://app.example.test"
    fake = FakeStripe()
    for name in ("create_customer", "create_checkout_url", "create_portal_url"):
        monkeypatch.setattr(stripe_api, name, getattr(fake, name))
    return fake


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="payer", email="payer@example.com")


@pytest.fixture
def client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def test_both_endpoints_require_a_session(api_client: APIClient) -> None:
    for url in (CHECKOUT, PORTAL):
        response = api_client.post(url)
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"


def test_checkout_creates_a_customer_and_returns_the_hosted_url(
    client: APIClient, user: User, fake_stripe: FakeStripe
) -> None:
    response = client.post(CHECKOUT)

    assert response.status_code == 200
    assert response.json() == {"url": "https://checkout.stripe.test/c/pay"}
    customer = StripeCustomer.objects.get()
    assert (customer.user, customer.livemode, customer.customer_id) == (user, False, "cus_new_1")
    assert fake_stripe.checkouts == [
        {
            "livemode": False,
            "customer_id": "cus_new_1",
            "price_id": "price_test_unit",
            "client_reference_id": str(user.pk),
            "success_url": "https://app.example.test/account?checkout=success",
            "cancel_url": "https://app.example.test/account",
        }
    ]


def test_checkout_reuses_the_existing_customer(
    client: APIClient, user: User, fake_stripe: FakeStripe
) -> None:
    StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_existing")

    client.post(CHECKOUT)
    client.post(CHECKOUT)

    assert fake_stripe.customers_created == []
    assert {c["customer_id"] for c in fake_stripe.checkouts} == {"cus_existing"}


def test_checkout_sends_a_user_with_a_live_plan_to_the_portal_instead(
    client: APIClient, user: User, fake_stripe: FakeStripe
) -> None:
    customer = StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_1")
    Subscription.objects.create(
        customer=customer,
        subscription_id="sub_1",
        livemode=False,
        status="active",
        current_period_end=datetime.now(UTC) + timedelta(days=5),
    )

    response = client.post(CHECKOUT)

    assert response.json() == {"url": "https://billing.stripe.test/p/session"}
    assert fake_stripe.checkouts == []


def test_portal_returns_the_session_url_for_the_users_customer(
    client: APIClient, user: User, fake_stripe: FakeStripe
) -> None:
    StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_1")

    response = client.post(PORTAL)

    assert response.status_code == 200
    assert response.json() == {"url": "https://billing.stripe.test/p/session"}
    assert fake_stripe.portals == [
        {
            "livemode": False,
            "customer_id": "cus_1",
            "return_url": "https://app.example.test/account",
        }
    ]


def test_portal_without_a_billing_account_is_a_404(
    client: APIClient, fake_stripe: FakeStripe
) -> None:
    response = client.post(PORTAL)

    assert response.status_code == 404
    assert response.json()["code"] == "no_billing_account"


def test_me_reports_pro_with_the_subscription_block(client: APIClient, user: User) -> None:
    customer = StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_1")
    period_end = datetime.now(UTC) + timedelta(days=20)
    Subscription.objects.create(
        customer=customer,
        subscription_id="sub_1",
        livemode=False,
        status="active",
        current_period_end=period_end,
        cancel_at_period_end=True,
    )

    body = client.get(ME).json()

    assert body["plan"] == "pro"
    assert body["usage"]["limit"] == 100
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["cancel_at_period_end"] is True
    assert datetime.fromisoformat(body["subscription"]["current_period_end"]) == period_end


def test_me_has_no_subscription_block_without_one(client: APIClient) -> None:
    body = client.get(ME).json()

    assert body["plan"] == "free"
    assert body["subscription"] is None


def test_me_shows_a_canceled_subscription_but_stays_free(client: APIClient, user: User) -> None:
    customer = StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_1")
    Subscription.objects.create(
        customer=customer,
        subscription_id="sub_1",
        livemode=False,
        status="canceled",
        current_period_end=datetime.now(UTC) - timedelta(days=1),
    )

    body = client.get(ME).json()

    assert body["plan"] == "free"
    assert body["subscription"]["status"] == "canceled"
