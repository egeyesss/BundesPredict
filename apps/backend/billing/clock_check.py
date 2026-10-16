"""Drives a Stripe test clock through a renewal and a declined renewal, checking synced rows."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from accounts import plans

from . import stripe_api, sync
from .models import StripeCustomer, Subscription

GOOD_CARD = "pm_card_visa"
# Attaches fine but declines every charge; the token form of card 4000 0000 0000 0341.
DECLINING_CARD = "pm_card_chargeCustomerFail"
RENEWAL_STEP = timedelta(days=32)


class CheckFailed(Exception):
    pass


def _expect(condition: bool, scenario: str, detail: str) -> None:
    if not condition:
        raise CheckFailed(f"{scenario}: {detail}")


def run(log: Callable[[str], None]) -> None:
    started = timezone.now()
    clock_id = stripe_api.clock_create(started)
    user = User.objects.create_user(
        username=f"clock-check-{uuid.uuid4().hex[:8]}", email="clock-check@example.com"
    )
    try:
        customer_id, subscription_id = stripe_api.clock_add_subscriber(
            clock_id=clock_id, email=user.email, payment_method=GOOD_CARD
        )
        StripeCustomer.objects.create(user=user, livemode=False, customer_id=customer_id)

        first = _sync(subscription_id)
        _expect(first.status == "active", "setup", f"expected active, got {first.status}")
        log(f"subscription {subscription_id} active, period ends {first.current_period_end:%F}")

        stripe_api.clock_advance(clock_id, started + RENEWAL_STEP)
        renewed = _sync(subscription_id)
        _expect(renewed.status == "active", "renewal", f"status {renewed.status}")
        _expect(
            renewed.current_period_end > first.current_period_end,
            "renewal",
            "current_period_end did not move forward",
        )
        _expect(plans.has_pro(user), "renewal", "user lost pro")
        log("renewal: ok")

        stripe_api.clock_set_payment_method(customer_id, DECLINING_CARD)
        stripe_api.clock_advance(clock_id, started + 2 * RENEWAL_STEP)
        failed = _sync(subscription_id)
        _expect(failed.status == "past_due", "failed payment", f"status {failed.status}")
        _expect(plans.has_pro(user), "failed payment", "past_due lost pro before period end")
        log("failed payment: ok")
    finally:
        stripe_api.clock_delete(clock_id)
        with transaction.atomic():
            user.delete()


def _sync(subscription_id: str) -> Subscription:
    subscription = sync.sync_subscription(False, subscription_id)
    if subscription is None:
        raise CheckFailed("sync: subscription not stored")
    return subscription
