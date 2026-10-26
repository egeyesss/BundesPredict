"""Plans and the daily limit are derived only from synced subscription rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from accounts import plans
from accounts.models import UserProfile
from billing import stripe_api
from billing.models import StripeCustomer, Subscription

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_live_keys(settings: Any) -> None:
    settings.STRIPE_SECRET_KEY_LIVE = ""


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="reader", email="reader@example.com")


def _subscribe(
    user: User,
    status: str,
    *,
    livemode: bool = False,
    period_end: datetime = NOW + timedelta(days=10),
    cancel_at_period_end: bool = False,
    subscription_id: str = "sub_1",
) -> Subscription:
    customer, _ = StripeCustomer.objects.get_or_create(
        user=user, livemode=livemode, defaults={"customer_id": f"cus_{livemode}_{user.pk}"}
    )
    return Subscription.objects.create(
        customer=customer,
        subscription_id=subscription_id,
        livemode=livemode,
        status=status,
        current_period_end=period_end,
        cancel_at_period_end=cancel_at_period_end,
    )


def test_a_user_without_a_subscription_is_free(user: User) -> None:
    assert plans.limit_for(user, now=NOW) == plans.FREE_DAILY_LIMIT
    assert plans.plan_for(user.profile, now=NOW) == "free"


@pytest.mark.parametrize("status", ["active", "trialing"])
def test_active_and_trialing_subscriptions_are_pro(user: User, status: str) -> None:
    _subscribe(user, status)

    assert plans.limit_for(user, now=NOW) == plans.PRO_DAILY_LIMIT == 100
    assert plans.plan_for(user.profile, now=NOW) == "pro"


def test_past_due_keeps_pro_until_current_period_end(user: User) -> None:
    subscription = _subscribe(user, "past_due", period_end=NOW + timedelta(hours=1))

    assert plans.plan_for(user.profile, now=NOW) == "pro"

    subscription.current_period_end = NOW - timedelta(seconds=1)
    subscription.save()
    assert plans.plan_for(user.profile, now=NOW) == "free"
    assert plans.limit_for(user, now=NOW) == plans.FREE_DAILY_LIMIT


@pytest.mark.parametrize(
    "status", ["canceled", "incomplete", "incomplete_expired", "unpaid", "paused"]
)
def test_other_statuses_are_free(user: User, status: str) -> None:
    _subscribe(user, status)

    assert plans.plan_for(user.profile, now=NOW) == "free"


def test_a_subscription_set_to_cancel_at_period_end_is_still_pro(user: User) -> None:
    _subscribe(user, "active", cancel_at_period_end=True)

    assert plans.plan_for(user.profile, now=NOW) == "pro"


def test_one_active_subscription_among_dead_ones_is_enough(user: User) -> None:
    _subscribe(user, "canceled", subscription_id="sub_old")
    _subscribe(user, "active", subscription_id="sub_new")

    assert plans.plan_for(user.profile, now=NOW) == "pro"


def test_other_users_subscriptions_do_not_count(user: User) -> None:
    other = User.objects.create_user(username="other", email="other@example.com")
    _subscribe(other, "active")

    assert plans.plan_for(user.profile, now=NOW) == "free"


def test_a_live_subscription_is_ignored_while_real_users_are_on_test_mode(user: User) -> None:
    _subscribe(user, "active", livemode=True)

    assert plans.plan_for(user.profile, now=NOW) == "free"


def test_a_test_subscription_is_ignored_once_live_keys_exist(user: User, settings: Any) -> None:
    settings.STRIPE_SECRET_KEY_LIVE = "sk_live_unit"
    _subscribe(user, "active", livemode=False)
    assert plans.plan_for(user.profile, now=NOW) == "free"

    _subscribe(user, "active", livemode=True, subscription_id="sub_live")
    assert plans.plan_for(user.profile, now=NOW) == "pro"


def test_demo_users_stay_demo_without_a_subscription_and_get_the_demo_cap(
    user: User,
) -> None:
    UserProfile.objects.filter(user=user).update(is_demo=True)
    user.refresh_from_db()

    assert plans.plan_for(user.profile, now=NOW) == "demo"
    assert plans.limit_for(user, now=NOW) == plans.DEMO_CHAT_LIMIT


def test_a_demo_user_with_a_test_subscription_is_pro_even_with_live_keys(
    user: User, settings: Any
) -> None:
    settings.STRIPE_SECRET_KEY_LIVE = "sk_live_unit"
    UserProfile.objects.filter(user=user).update(is_demo=True)
    user.refresh_from_db()
    _subscribe(user, "active", livemode=False)

    assert plans.plan_for(user.profile, now=NOW) == "pro"


def test_without_an_explicit_now_the_current_time_is_used(user: User) -> None:
    _subscribe(user, "past_due", period_end=timezone.now() + timedelta(days=1))

    assert plans.plan_for(user.profile) == "pro"


class TestStripeMode:
    def test_real_users_use_test_mode_until_live_keys_are_configured(self, user: User) -> None:
        assert stripe_api.livemode_for(user) is False

    def test_real_users_switch_to_live_once_a_live_key_exists(
        self, user: User, settings: Any
    ) -> None:
        settings.STRIPE_SECRET_KEY_LIVE = "sk_live_unit"

        assert stripe_api.livemode_for(user) is True

    def test_demo_users_always_use_test_mode(self, user: User, settings: Any) -> None:
        settings.STRIPE_SECRET_KEY_LIVE = "sk_live_unit"
        UserProfile.objects.filter(user=user).update(is_demo=True)
        user.refresh_from_db()

        assert stripe_api.livemode_for(user) is False
