from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Q, QuerySet
from django.utils import timezone

from billing import stripe_api
from billing.models import Subscription

from .models import UserProfile

FREE_DAILY_LIMIT = 3
PRO_DAILY_LIMIT = 100


def _user_subscriptions(user: AbstractBaseUser) -> QuerySet[Subscription]:
    return Subscription.objects.filter(
        customer__user_id=user.pk, livemode=stripe_api.livemode_for(user)
    )


def _grants_pro(now: datetime) -> Q:
    """Active or trialing, or past_due until the paid period runs out."""
    return Q(status__in=["active", "trialing"]) | Q(status="past_due", current_period_end__gt=now)


def has_pro(user: AbstractBaseUser, now: datetime | None = None) -> bool:
    return _user_subscriptions(user).filter(_grants_pro(now or timezone.now())).exists()


def current_subscription(
    user: AbstractBaseUser, now: datetime | None = None
) -> Subscription | None:
    """The plan-granting subscription if there is one, else the most recently synced."""
    subscriptions = _user_subscriptions(user)
    granting = subscriptions.filter(_grants_pro(now or timezone.now())).first()
    return granting or subscriptions.order_by("-updated_at").first()


def limit_for(user: AbstractBaseUser, now: datetime | None = None) -> int:
    """Chats per UTC day. Demo users keep the free limit; their own cap comes with the demo flow."""
    return PRO_DAILY_LIMIT if has_pro(user, now) else FREE_DAILY_LIMIT


def plan_for(profile: UserProfile, now: datetime | None = None) -> str:
    if has_pro(profile.user, now):
        return "pro"
    return "demo" if profile.is_demo else "free"
