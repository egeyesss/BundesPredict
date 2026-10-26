"""purge_demo_users removes expired demo accounts and everything tied to them."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import Client, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import DailyUsage
from billing.models import StripeCustomer, Subscription
from chat.models import Conversation, Message
from ops import demo
from ops.models import DemoStartCount
from predictions.models import Prediction
from track_record.news_edge import build_news_edge

pytestmark = pytest.mark.django_db

RunCommand = Callable[..., str]


def started(ip: str = "203.0.113.7") -> User:
    return demo.start_demo(client_ip=ip)


def expire(user: User, *, hours_ago: float = 1) -> None:
    user.profile.demo_expires_at = timezone.now() - timedelta(hours=hours_ago)
    user.profile.save()


def attach_everything(user: User) -> Client:
    """Billing rows, an allauth address, usage and a signed-in browser session."""
    customer = StripeCustomer.objects.create(
        user=user, livemode=False, customer_id=f"cus_{user.pk}"
    )
    Subscription.objects.create(
        customer=customer,
        subscription_id=f"sub_{user.pk}",
        livemode=False,
        status="active",
        current_period_end=timezone.now() + timedelta(days=5),
    )
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    DailyUsage.objects.create(user=user, day=date(2026, 3, 10), chats_used=2)
    browser = Client()
    browser.force_login(user)
    return browser


def test_an_expired_demo_user_and_all_their_rows_are_deleted(
    demo_world: None, run_command: RunCommand
) -> None:
    user = started()
    browser = attach_everything(user)
    expire(user)
    assert Prediction.objects.filter(user=user).count() == 2

    output = run_command("purge_demo_users")

    assert not User.objects.filter(pk=user.pk).exists()
    assert not Conversation.objects.exists()
    assert not Message.objects.exists()
    assert not Prediction.objects.exists()
    assert not DailyUsage.objects.exists()
    assert not StripeCustomer.objects.exists()
    assert not Subscription.objects.exists()
    assert not EmailAddress.objects.exists()
    assert (
        browser.get("/api/v1/me", headers={"x-proxy-secret": settings.PROXY_SECRET}).status_code
        == 401
    )
    assert output.count("\n") == 0
    assert "1 demo user" in output


def test_unexpired_demo_users_are_left_alone(demo_world: None, run_command: RunCommand) -> None:
    live = started("203.0.113.1")
    attach_everything(live)
    stale = started("203.0.113.2")
    expire(stale)

    run_command("purge_demo_users")

    assert User.objects.filter(pk=live.pk).exists()
    assert not User.objects.filter(pk=stale.pk).exists()
    assert Conversation.objects.filter(user=live).count() == 2
    assert Prediction.objects.filter(user=live).count() == 2
    assert Session.objects.count() == 1


def test_real_users_are_never_touched(demo_world: None, run_command: RunCommand) -> None:
    real = User.objects.create_user(username="real", email="real@example.com")
    attach_everything(real)
    conversation = Conversation.objects.create(user=real, title="mine")
    Message.objects.create(conversation=conversation, role="user", content="hi")
    real.profile.demo_expires_at = timezone.now() - timedelta(days=3)
    real.profile.save()
    stale = started()
    expire(stale)

    run_command("purge_demo_users")

    assert User.objects.filter(pk=real.pk).exists()
    assert Conversation.objects.filter(user=real).exists()
    assert Message.objects.filter(conversation=conversation).exists()
    assert DailyUsage.objects.filter(user=real).exists()
    assert Subscription.objects.filter(customer__user=real).exists()
    assert Session.objects.count() == 1


def test_purged_predictions_do_not_linger_in_the_news_edge(
    demo_world: None, run_command: RunCommand
) -> None:
    user = started()
    expire(user)

    run_command("purge_demo_users")

    assert build_news_edge()["n_logged"] == 0
    assert not Prediction.objects.filter(user__isnull=True).exists()


def test_old_start_counters_go_too(demo_world: None, run_command: RunCommand) -> None:
    today = datetime.now(UTC).date()
    DemoStartCount.objects.create(scope="site", day=today - timedelta(days=3), starts=9)
    DemoStartCount.objects.create(scope="site", day=today - timedelta(days=1), starts=4)

    run_command("purge_demo_users")

    assert list(DemoStartCount.objects.values_list("starts", flat=True)) == [4]


def test_a_run_with_nothing_to_do_says_so(demo_world: None, run_command: RunCommand) -> None:
    assert "0 demo users" in run_command("purge_demo_users")


def test_a_demo_session_goes_even_when_the_purge_cannot_read_sessions(
    api_client: APIClient, demo_world: None
) -> None:
    # The scheduled workflow runs with a placeholder SECRET_KEY, so it can't decode session data.
    response = api_client.post("/api/v1/demo/start", headers={"x-client-ip": "203.0.113.7"})
    session_key = response.cookies["sessionid"].value

    with override_settings(SECRET_KEY="not-the-key-that-signed-the-session"):
        report = demo.purge_expired(now=timezone.now() + timedelta(hours=25))

    assert report.users == 1
    assert not Session.objects.filter(pk=session_key).exists()
