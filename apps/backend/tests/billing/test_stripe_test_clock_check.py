"""The test-clock command: scripted Stripe answers, real sync rows, and cleanup either way."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from billing import stripe_api
from billing.models import StripeCustomer, Subscription

pytestmark = pytest.mark.django_db

START = datetime(2026, 11, 1, tzinfo=UTC)


class FakeClock:
    """Plays the Stripe side: a renewal that pays, then a renewal whose card is declined."""

    def __init__(self, *, declines: bool = True) -> None:
        self.declines = declines
        self.frozen = START
        self.status = "active"
        self.period_end = START + timedelta(days=30)
        self.payment_method = "pm_card_visa"
        self.deleted: list[str] = []

    def create(self, frozen_time: datetime) -> str:
        self.frozen = frozen_time
        return "clock_1"

    def add_subscriber(self, *, clock_id: str, email: str, payment_method: str) -> tuple[str, str]:
        self.payment_method = payment_method
        return "cus_clock", "sub_clock"

    def set_payment_method(self, customer_id: str, payment_method: str) -> None:
        self.payment_method = payment_method

    def advance(self, clock_id: str, frozen_time: datetime) -> None:
        self.frozen = frozen_time
        if self.payment_method == "pm_card_visa" or not self.declines:
            self.period_end += timedelta(days=30)
        else:
            self.status = "past_due"
            self.period_end += timedelta(days=30)

    def delete(self, clock_id: str) -> None:
        self.deleted.append(clock_id)

    def fetch(self, livemode: bool, subscription_id: str) -> stripe_api.SubscriptionSnapshot:
        return stripe_api.SubscriptionSnapshot(
            subscription_id, "cus_clock", self.status, self.period_end, False
        )


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch, settings: Any) -> FakeClock:
    settings.STRIPE_SECRET_KEY_TEST = "sk_test_unit"
    settings.STRIPE_PRICE_ID_TEST = "price_test_unit"
    fake = FakeClock()
    monkeypatch.setattr(stripe_api, "clock_create", fake.create)
    monkeypatch.setattr(stripe_api, "clock_add_subscriber", fake.add_subscriber)
    monkeypatch.setattr(stripe_api, "clock_set_payment_method", fake.set_payment_method)
    monkeypatch.setattr(stripe_api, "clock_advance", fake.advance)
    monkeypatch.setattr(stripe_api, "clock_delete", fake.delete)
    monkeypatch.setattr(stripe_api, "fetch_subscription", fake.fetch)
    return fake


def _run() -> str:
    out = StringIO()
    call_command("stripe_test_clock_check", stdout=out)
    return out.getvalue()


def test_a_passing_check_reports_both_scenarios_and_cleans_up(fake_clock: FakeClock) -> None:
    output = _run()

    assert "renewal: ok" in output
    assert "failed payment: ok" in output
    assert fake_clock.deleted == ["clock_1"]
    assert not User.objects.exists()
    assert not StripeCustomer.objects.exists()
    assert not Subscription.objects.exists()


def test_a_wrong_outcome_fails_the_command_and_still_cleans_up(fake_clock: FakeClock) -> None:
    fake_clock.declines = False

    with pytest.raises(CommandError, match="failed payment"):
        _run()

    assert fake_clock.deleted == ["clock_1"]
    assert not User.objects.exists()


def test_the_command_refuses_to_run_without_a_test_key(settings: Any) -> None:
    settings.STRIPE_SECRET_KEY_TEST = ""

    with pytest.raises(CommandError, match="STRIPE_SECRET_KEY_TEST"):
        _run()
