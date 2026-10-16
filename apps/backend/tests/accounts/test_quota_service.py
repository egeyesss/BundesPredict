"""The daily chat quota: one atomic statement per consume, day keyed in UTC."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext

from accounts import plans, quota
from accounts.models import DailyUsage

LIMIT = plans.FREE_DAILY_LIMIT
NOON = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(username="quota-user", email="quota@example.com")


def _used(user: User, now: datetime = NOON) -> int:
    row = DailyUsage.objects.filter(user=user, day=now.date()).first()
    return row.chats_used if row else 0


def test_consume_counts_up_to_the_limit_then_refuses(user: User) -> None:
    results = [quota.consume(user, now=NOON) for _ in range(LIMIT + 2)]

    assert [r.used if r else None for r in results] == [*range(1, LIMIT + 1), None, None]
    assert _used(user) == LIMIT


def test_consume_returns_the_limit_and_the_next_utc_midnight(user: User) -> None:
    usage = quota.consume(user, now=NOON)

    assert usage is not None
    assert usage.limit == LIMIT
    assert usage.resets_at == datetime(2026, 3, 11, tzinfo=UTC)


def test_a_refused_consume_leaves_the_counter_alone(user: User) -> None:
    DailyUsage.objects.create(user=user, day=NOON.date(), chats_used=LIMIT)

    assert quota.consume(user, now=NOON) is None
    assert _used(user) == LIMIT


def test_consume_with_a_zero_limit_never_inserts(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plans, "limit_for", lambda _user: 0)

    assert quota.consume(user, now=NOON) is None
    assert not DailyUsage.objects.filter(user=user).exists()


def test_refund_gives_one_chat_back(user: User) -> None:
    quota.consume(user, now=NOON)
    quota.consume(user, now=NOON)

    quota.refund(user, now=NOON)

    assert _used(user) == 1


def test_refund_never_goes_below_zero(user: User) -> None:
    quota.refund(user, now=NOON)
    assert _used(user) == 0

    quota.consume(user, now=NOON)
    quota.refund(user, now=NOON)
    quota.refund(user, now=NOON)
    assert _used(user) == 0


def test_the_counter_resets_at_the_utc_day_boundary(user: User) -> None:
    last_second = datetime(2026, 3, 10, 23, 59, 59, tzinfo=UTC)
    for _ in range(LIMIT):
        quota.consume(user, now=last_second)
    assert quota.consume(user, now=last_second) is None

    next_day = last_second + timedelta(seconds=1)
    usage = quota.consume(user, now=next_day)

    assert usage is not None
    assert usage.used == 1
    assert _used(user, last_second) == LIMIT


def test_current_reports_zero_without_a_row_and_does_not_create_one(user: User) -> None:
    usage = quota.current(user, now=NOON)

    assert (usage.used, usage.limit) == (0, LIMIT)
    assert not DailyUsage.objects.filter(user=user).exists()


def test_current_reflects_consumed_chats(user: User) -> None:
    quota.consume(user, now=NOON)
    quota.consume(user, now=NOON)

    assert quota.current(user, now=NOON).used == 2


def test_consume_is_a_single_statement(user: User) -> None:
    with CaptureQueriesContext(connection) as captured:
        quota.consume(user, now=NOON)

    # The plan lookup reads subscriptions first; the counter itself is still one statement.
    counter_queries = [q["sql"] for q in captured if "accounts_dailyusage" in q["sql"]]
    assert len(counter_queries) == 1
    assert "ON CONFLICT" in counter_queries[0]


def _race_two_consumers(user: User) -> tuple[list[quota.Usage | None], list[BaseException]]:
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
def test_two_concurrent_requests_at_limit_minus_one_let_exactly_one_through() -> None:
    # Repeated because a racy read-then-write only loses the race some of the time.
    for round_number in range(25):
        user = User.objects.create_user(username=f"racer-{round_number}")
        DailyUsage.objects.create(user=user, day=NOON.date(), chats_used=LIMIT - 1)

        outcomes, errors = _race_two_consumers(user)

        assert not errors
        assert sorted(outcome is not None for outcome in outcomes) == [False, True]
        assert _used(user) == LIMIT
