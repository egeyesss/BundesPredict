"""Demo users get 10 chats for the whole life of the account, whatever the plan."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connections
from rest_framework.test import APIClient

from accounts import plans, quota
from accounts.models import DailyUsage
from billing.models import StripeCustomer, Subscription

NOON = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
EXPIRES = NOON + timedelta(hours=20)
CAP = plans.DEMO_CHAT_LIMIT


def make_demo_user(username: str = "demo-quota") -> User:
    user = User.objects.create_user(username=username, email=f"{username}@example.com")
    user.profile.is_demo = True
    user.profile.demo_expires_at = EXPIRES
    user.profile.save()
    return user


@pytest.fixture
def demo_user(db: None) -> User:
    return make_demo_user()


def make_pro(user: User) -> None:
    customer = StripeCustomer.objects.create(user=user, livemode=False, customer_id="cus_demo")
    Subscription.objects.create(
        customer=customer,
        subscription_id="sub_demo",
        livemode=False,
        status="active",
        current_period_end=NOON + timedelta(days=20),
    )


def lifetime_used(user: User) -> int:
    return sum(DailyUsage.objects.filter(user=user).values_list("chats_used", flat=True))


def test_the_cap_is_ten() -> None:
    assert CAP == 10


def test_the_eleventh_chat_is_refused(demo_user: User) -> None:
    results = [quota.consume(demo_user, now=NOON) for _ in range(CAP + 1)]

    assert [r.used if r else None for r in results] == [*range(1, CAP + 1), None]
    assert lifetime_used(demo_user) == CAP


def test_utc_midnight_does_not_hand_out_a_fresh_allowance(demo_user: User) -> None:
    late = NOON.replace(hour=23, minute=50)
    for _ in range(6):
        assert quota.consume(demo_user, now=late) is not None

    next_day = late + timedelta(minutes=20)
    after_midnight = [quota.consume(demo_user, now=next_day) for _ in range(5)]

    assert [r.used if r else None for r in after_midnight] == [7, 8, 9, 10, None]
    assert quota.consume(demo_user, now=next_day + timedelta(days=1)) is None


def test_a_test_mode_checkout_does_not_lift_the_cap(demo_user: User) -> None:
    make_pro(demo_user)

    assert plans.plan_for(demo_user.profile) == "pro"
    assert plans.limit_for(demo_user) == CAP
    results = [quota.consume(demo_user, now=NOON) for _ in range(CAP + 1)]
    assert results[-1] is None
    assert results[-2] is not None


def test_usage_counts_the_whole_life_and_resets_when_the_account_expires(demo_user: User) -> None:
    quota.consume(demo_user, now=NOON - timedelta(days=1))
    quota.consume(demo_user, now=NOON)
    quota.consume(demo_user, now=NOON)

    usage = quota.current(demo_user, now=NOON)

    assert usage == quota.Usage(used=3, limit=CAP, resets_at=EXPIRES)


def test_a_refund_gives_the_chat_back(demo_user: User) -> None:
    for _ in range(CAP):
        quota.consume(demo_user, now=NOON)
    assert quota.consume(demo_user, now=NOON) is None

    quota.refund(demo_user, now=NOON)

    assert quota.consume(demo_user, now=NOON) is not None


def test_me_shows_the_lifetime_numbers(demo_user: User) -> None:
    quota.consume(demo_user)
    client = APIClient(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    client.force_authenticate(user=demo_user)

    usage = client.get("/api/v1/me").json()["usage"]

    assert usage["used"] == 1
    assert usage["limit"] == CAP
    assert datetime.fromisoformat(usage["resets_at"]) == EXPIRES


def test_other_users_keep_the_daily_limit_and_midnight_reset(db: None) -> None:
    free = User.objects.create_user(username="plain", email="plain@example.com")

    assert plans.limit_for(free) == plans.FREE_DAILY_LIMIT
    assert quota.current(free, now=NOON).resets_at == datetime(2026, 3, 11, tzinfo=UTC)


def race_two_consumers(user: User) -> tuple[list[quota.Usage | None], list[BaseException]]:
    """Run two `consume` calls at once, each thread on its own database connection."""
    barrier = threading.Barrier(2)
    outcomes: list[quota.Usage | None] = []
    errors: list[BaseException] = []

    def attempt() -> None:
        try:
            barrier.wait(timeout=10)
            outcomes.append(quota.consume(user, now=NOON))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return outcomes, errors


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_chats_at_nine_let_exactly_one_through() -> None:
    # Repeated because a racy read-then-write only loses the race some of the time.
    for round_number in range(25):
        user = make_demo_user(f"racer-{round_number}")
        for _ in range(CAP - 1):
            quota.consume(user, now=NOON)

        outcomes, errors = race_two_consumers(user)

        assert not errors
        assert sorted(outcome is not None for outcome in outcomes) == [False, True]
        assert lifetime_used(user) == CAP


def test_the_stream_answers_402_once_the_demo_chats_are_used_up(
    demo_user: User, demo_world: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("predictions.views.get_llm_client", lambda: object())
    for _ in range(CAP):
        quota.consume(demo_user)
    client = APIClient(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    client.force_authenticate(user=demo_user)

    response = client.post("/api/v1/predict/stream", {"query": "Who wins?"}, format="json")

    assert response.status_code == 402
    body = response.json()
    assert body["code"] == "quota_exceeded"
    assert body["usage"]["used"] == CAP
    assert body["usage"]["limit"] == CAP
    assert "demo" in body["message"]
