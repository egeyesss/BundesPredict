"""`/api/v1/admin/metrics`: who may read it and what the numbers count."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.models import DailyUsage
from billing.models import StripeCustomer, StripeEvent, Subscription
from football.models import ModelRun, Team
from ops.models import WebhookFailure
from predictions.models import Prediction

URL = "/api/v1/admin/metrics"
NOW = datetime.now(UTC)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def test_mode_for_everyone(settings: Any) -> None:
    settings.STRIPE_SECRET_KEY_LIVE = ""


def make_user(name: str, **fields: Any) -> User:
    return User.objects.create_user(username=name, email=f"{name}@example.com", **fields)


def subscribe(
    user: User,
    *,
    status: str = "active",
    livemode: bool = True,
    updated_days_ago: int = 0,
    period_end: datetime | None = None,
) -> Subscription:
    customer, _ = StripeCustomer.objects.get_or_create(
        user=user, livemode=livemode, defaults={"customer_id": f"cus_{user.pk}_{livemode}"}
    )
    subscription = Subscription.objects.create(
        customer=customer,
        subscription_id=f"sub_{user.pk}_{livemode}_{status}",
        livemode=livemode,
        status=status,
        current_period_end=period_end or NOW + timedelta(days=10),
    )
    Subscription.objects.filter(pk=subscription.pk).update(
        updated_at=NOW - timedelta(days=updated_days_ago)
    )
    return subscription


def client_for(user: User) -> APIClient:
    from django.conf import settings

    client = APIClient()
    client.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_client(db: None) -> APIClient:
    return client_for(make_user("boss", is_staff=True))


def test_signed_out_is_401(api_client: APIClient) -> None:
    assert api_client.get(URL).status_code == 401


def test_a_regular_user_is_403(db: None) -> None:
    response = client_for(make_user("reader")).get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_staff_and_superusers_are_let_in() -> None:
    assert client_for(make_user("staff", is_staff=True)).get(URL).status_code == 200
    assert client_for(make_user("root", is_superuser=True)).get(URL).status_code == 200


def test_an_empty_database_returns_zeros_not_errors(staff_client: APIClient) -> None:
    body = staff_client.get(URL).json()

    assert body["masked"] is False
    assert body["active_subscribers"] == 0
    assert body["mrr_cents"] == 0
    assert body["monthly_churn"] == 0
    assert body["cost_to_revenue_per_pro_user"] is None
    assert len(body["chats_per_day"]) == 30
    assert body["webhook_failures"] == []


def test_mrr_counts_live_subscriptions_only_and_test_mode_is_reported_apart(
    staff_client: APIClient,
) -> None:
    subscribe(make_user("live1"), livemode=True)
    subscribe(make_user("live2"), livemode=True, status="past_due")
    subscribe(make_user("test1"), livemode=False)
    subscribe(make_user("test2"), livemode=False)
    subscribe(make_user("test3"), livemode=False)
    subscribe(make_user("gone"), livemode=True, status="canceled")

    body = staff_client.get(URL).json()

    assert body["active_subscribers"] == 2
    assert body["mrr_cents"] == 1000
    assert body["test_mode"] == {"active_subscribers": 3, "mrr_cents": 1500}


def test_past_due_after_the_paid_period_does_not_count(staff_client: APIClient) -> None:
    subscribe(make_user("lapsed"), status="past_due", period_end=NOW - timedelta(days=1))

    assert staff_client.get(URL).json()["mrr_cents"] == 0


def test_churn_is_cancellations_in_30_days_over_active_plus_cancelled(
    staff_client: APIClient,
) -> None:
    for name in ("a", "b", "c"):
        subscribe(make_user(name))
    subscribe(make_user("recent"), status="canceled", updated_days_ago=5)
    subscribe(make_user("old"), status="canceled", updated_days_ago=45)

    assert staff_client.get(URL).json()["monthly_churn"] == pytest.approx(1 / 4)


def test_signups_skip_demo_users_and_respect_the_windows(staff_client: APIClient) -> None:
    make_user("fresh")
    older = make_user("older")
    User.objects.filter(pk=older.pk).update(date_joined=NOW - timedelta(days=20))
    ancient = make_user("ancient")
    User.objects.filter(pk=ancient.pk).update(date_joined=NOW - timedelta(days=200))
    visitor = make_user("visitor")
    visitor.profile.is_demo = True
    visitor.profile.save()

    body = staff_client.get(URL).json()

    assert (body["signups_7d"], body["signups_30d"]) == (2, 3)


def test_chats_per_day_split_by_plan(staff_client: APIClient) -> None:
    pro, free, demo = make_user("pro"), make_user("free"), make_user("demo")
    demo.profile.is_demo = True
    demo.profile.save()
    subscribe(pro, livemode=False)
    today = NOW.date()
    for user, used in ((pro, 4), (free, 2), (demo, 1)):
        DailyUsage.objects.create(user=user, day=today, chats_used=used)
    DailyUsage.objects.create(user=free, day=today - timedelta(days=1), chats_used=3)

    rows = {row["day"]: row for row in staff_client.get(URL, {"days": 7}).json()["chats_per_day"]}

    assert len(rows) == 7
    assert rows[today.isoformat()] == {"day": today.isoformat(), "free": 2, "pro": 4, "demo": 1}
    assert rows[(today - timedelta(days=1)).isoformat()]["free"] == 3
    assert rows[(today - timedelta(days=2)).isoformat()] == {
        "day": (today - timedelta(days=2)).isoformat(),
        "free": 0,
        "pro": 0,
        "demo": 0,
    }


@pytest.mark.parametrize("days", ["0", "8", "abc"])
def test_an_unsupported_range_is_a_400(staff_client: APIClient, days: str) -> None:
    assert staff_client.get(URL, {"days": days}).status_code == 400


def seed_prediction(user: User, cost: str, days_ago: int = 1) -> None:
    home, _ = Team.objects.get_or_create(name="Home")
    away, _ = Team.objects.get_or_create(name="Away")
    run = ModelRun.objects.first() or ModelRun.objects.create(
        model_type="dixon_coles", xi=0, rho=0, home_adv=0, log_likelihood=0, n_matches=1
    )
    prediction = Prediction.objects.create(
        user=user,
        model_run=run,
        home=home,
        away=away,
        p_home=0.4,
        p_draw=0.3,
        p_away=0.3,
        exp_home_goals=1,
        exp_away_goals=1,
        base_p_home=0.4,
        base_p_draw=0.3,
        base_p_away=0.3,
        cost_usd=Decimal(cost),
    )
    Prediction.objects.filter(pk=prediction.pk).update(created_at=NOW - timedelta(days=days_ago))


def test_llm_cost_per_user_and_cost_to_revenue_per_pro_user(staff_client: APIClient) -> None:
    heavy, light, free = make_user("heavy"), make_user("light"), make_user("freeloader")
    subscribe(heavy, livemode=False)
    subscribe(light, livemode=False)
    seed_prediction(heavy, "3.000000")
    seed_prediction(heavy, "1.000000")
    seed_prediction(light, "0.910000")
    seed_prediction(free, "0.090000")
    seed_prediction(free, "50.000000", days_ago=60)

    body = staff_client.get(URL).json()

    assert body["llm_cost_per_user_cents"] == pytest.approx((400 + 91 + 9) / 3)
    assert body["cost_to_revenue_per_pro_user"] == pytest.approx((4.91) / (2 * 4.55))
    assert [row["cost_cents"] for row in body["pro_user_costs"]] == [400, 91]
    assert body["pro_user_costs"][0]["email"] == "heavy@example.com"


def test_failed_payments_list_past_due_subscribers(staff_client: APIClient) -> None:
    subscribe(make_user("late"), status="past_due", updated_days_ago=2)

    row = staff_client.get(URL).json()["failed_payments"][0]

    assert row["email"] == "late@example.com"
    assert row["amount_cents"] == 500


def test_webhook_failures_hide_events_that_a_retry_later_processed(
    staff_client: APIClient,
) -> None:
    WebhookFailure.objects.create(
        event_id="evt_bad", type="invoice.paid", livemode=True, error="sub not found"
    )
    WebhookFailure.objects.create(
        event_id="evt_fixed", type="invoice.paid", livemode=True, error="timeout"
    )
    StripeEvent.objects.create(event_id="evt_fixed", type="invoice.paid", livemode=True)
    StripeEvent.objects.create(event_id="evt_ok", type="invoice.paid", livemode=False)

    body = staff_client.get(URL).json()

    assert [row["event_id"] for row in body["webhook_failures"]] == ["evt_bad"]
    assert body["webhook_failures"][0]["error"] == "sub not found"
    statuses = {row["event_id"]: row["status"] for row in body["webhook_events"]}
    assert statuses == {"evt_bad": "failed", "evt_fixed": "processed", "evt_ok": "processed"}


class TestDemoViewer:
    @pytest.fixture
    def demo_client(self) -> APIClient:
        viewer = make_user("viewer")
        viewer.profile.is_demo = True
        viewer.profile.save()
        return client_for(viewer)

    def test_a_demo_user_gets_the_numbers_with_masked_emails(self, demo_client: APIClient) -> None:
        subscribe(make_user("late"), status="past_due")
        pro = make_user("payer")
        subscribe(pro, livemode=False)
        seed_prediction(pro, "1.000000")

        body = demo_client.get(URL).json()

        assert body["masked"] is True
        assert body["failed_payments"][0]["email"] == "l•••@example.com"
        assert body["pro_user_costs"][0]["email"] == "p•••@example.com"
        assert "late@example.com" not in str(body)

    def test_a_demo_user_cannot_write(self, demo_client: APIClient) -> None:
        assert demo_client.post(URL, {}, format="json").status_code == 405


def test_the_day_axis_ends_today(staff_client: APIClient) -> None:
    days = [row["day"] for row in staff_client.get(URL).json()["chats_per_day"]]

    assert days[-1] == date.today().isoformat() or days[-1] == NOW.date().isoformat()
