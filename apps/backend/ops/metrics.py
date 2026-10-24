"""The numbers behind `/api/v1/admin/metrics`, computed straight from the app's own tables."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from accounts.models import DailyUsage
from billing.models import StripeEvent, Subscription
from predictions.models import Prediction

from .models import WebhookFailure

PRO_PRICE_CENTS = 500
# 5.00 less Stripe's 2.9% + 0.30 card fee, the line the cost chart draws.
PRO_NET_REVENUE_CENTS = 455
CHURN_WINDOW_DAYS = 30
COST_WINDOW_DAYS = 30
TOP_COST_USERS = 10
RECENT_ROWS = 10
UNPAID_STATUSES = ("past_due",)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}•••@{domain}"


def _paying(now: datetime) -> Q:
    """Active, or past_due while the paid period has not run out."""
    return Q(status="active") | Q(status="past_due", current_period_end__gt=now)


def _paying_subscribers(livemode: bool, now: datetime) -> QuerySet[Subscription]:
    return Subscription.objects.filter(_paying(now), livemode=livemode)


def _mode_summary(livemode: bool, now: datetime) -> dict[str, int]:
    count = _paying_subscribers(livemode, now).count()
    return {"active_subscribers": count, "mrr_cents": count * PRO_PRICE_CENTS}


def _monthly_churn(now: datetime) -> float:
    lost = Subscription.objects.filter(
        livemode=True,
        status="canceled",
        updated_at__gte=now - timedelta(days=CHURN_WINDOW_DAYS),
    ).count()
    active = _paying_subscribers(True, now).count()
    return lost / (active + lost) if active + lost else 0.0


def _pro_user_ids(now: datetime) -> set[int]:
    """Users on Pro in the Stripe mode they bill in: demo users always in test mode."""
    live_key = bool(settings.STRIPE_SECRET_KEY_LIVE)
    in_their_mode = Q(livemode=live_key, customer__user__profile__is_demo=False) | Q(
        livemode=False, customer__user__profile__is_demo=True
    )
    granting = Q(status__in=["active", "trialing"]) | Q(
        status="past_due", current_period_end__gt=now
    )
    return set(
        Subscription.objects.filter(granting, in_their_mode).values_list(
            "customer__user_id", flat=True
        )
    )


def _chats_per_day(days: int, now: datetime, pro_ids: set[int]) -> list[dict[str, Any]]:
    today = now.date()
    first = today - timedelta(days=days - 1)
    demo_ids = set(User.objects.filter(profile__is_demo=True).values_list("pk", flat=True))
    totals: dict[Any, dict[str, int]] = defaultdict(lambda: {"free": 0, "pro": 0, "demo": 0})
    for user_id, day, used in DailyUsage.objects.filter(day__gte=first, day__lte=today).values_list(
        "user_id", "day", "chats_used"
    ):
        plan = "pro" if user_id in pro_ids else "demo" if user_id in demo_ids else "free"
        totals[day][plan] += used
    return [
        {"day": first + timedelta(days=offset), **totals[first + timedelta(days=offset)]}
        for offset in range(days)
    ]


def _llm_costs(now: datetime, pro_ids: set[int], masked: bool) -> dict[str, Any]:
    since = now - timedelta(days=COST_WINDOW_DAYS)
    per_user = {
        row["user_id"]: row["cost"]
        for row in Prediction.objects.filter(
            created_at__gte=since, user__isnull=False, cost_usd__isnull=False
        )
        .values("user_id")
        .annotate(cost=Sum("cost_usd"))
    }
    total_cents = float(sum(per_user.values())) * 100
    pro_cost_cents = float(sum(cost for uid, cost in per_user.items() if uid in pro_ids)) * 100
    emails = dict(User.objects.filter(pk__in=pro_ids).values_list("pk", "email"))
    top = sorted(
        ((uid, cost) for uid, cost in per_user.items() if uid in pro_ids),
        key=lambda pair: pair[1],
        reverse=True,
    )[:TOP_COST_USERS]
    return {
        "llm_cost_per_user_cents": total_cents / len(per_user) if per_user else 0.0,
        "cost_to_revenue_per_pro_user": (
            pro_cost_cents / (len(pro_ids) * PRO_NET_REVENUE_CENTS) if pro_ids else None
        ),
        "pro_user_costs": [
            {
                "email": mask_email(emails[uid]) if masked else emails[uid],
                "cost_cents": round(float(cost) * 100),
            }
            for uid, cost in top
        ],
    }


def _webhooks() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    processed_ids = set(
        StripeEvent.objects.filter(
            event_id__in=WebhookFailure.objects.values("event_id")
        ).values_list("event_id", flat=True)
    )
    failures = [
        {
            "event_id": f.event_id,
            "type": f.type,
            "livemode": f.livemode,
            "error": f.error,
            "received_at": f.last_failed_at,
        }
        for f in WebhookFailure.objects.exclude(event_id__in=processed_ids)[:RECENT_ROWS]
    ]
    events = [{**failure, "status": "failed"} for failure in failures] + [
        {
            "event_id": e.event_id,
            "type": e.type,
            "livemode": e.livemode,
            "error": "",
            "received_at": e.received_at,
            "status": "processed",
        }
        for e in StripeEvent.objects.order_by("-received_at")[:RECENT_ROWS]
    ]
    events.sort(key=lambda row: cast(datetime, row["received_at"]), reverse=True)
    return failures, events[:RECENT_ROWS]


def _failed_payments(masked: bool) -> list[dict[str, Any]]:
    unpaid = Subscription.objects.filter(status__in=UNPAID_STATUSES).select_related(
        "customer__user"
    )
    return [
        {
            "email": mask_email(s.customer.user.email) if masked else s.customer.user.email,
            "livemode": s.livemode,
            "amount_cents": PRO_PRICE_CENTS,
            "failed_at": s.updated_at,
        }
        for s in unpaid.order_by("-updated_at")[:RECENT_ROWS]
    ]


def build_metrics(*, days: int, masked: bool, now: datetime | None = None) -> dict[str, Any]:
    now = now or timezone.now().astimezone(UTC)
    pro_ids = _pro_user_ids(now)
    live = _mode_summary(True, now)
    signups = User.objects.filter(profile__is_demo=False)
    failures, events = _webhooks()
    return {
        "generated_at": now,
        "masked": masked,
        **live,
        "test_mode": _mode_summary(False, now),
        "signups_7d": signups.filter(date_joined__gte=now - timedelta(days=7)).count(),
        "signups_30d": signups.filter(date_joined__gte=now - timedelta(days=30)).count(),
        "monthly_churn": _monthly_churn(now),
        "chats_per_day": _chats_per_day(days, now, pro_ids),
        **_llm_costs(now, pro_ids, masked),
        "webhook_failures": failures,
        "webhook_events": events,
        "failed_payments": _failed_payments(masked),
    }
