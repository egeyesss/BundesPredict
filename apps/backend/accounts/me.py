"""The `Me` payload shared by `/api/v1/me` and the demo start."""

from __future__ import annotations

from django.contrib.auth.models import User

from . import plans, quota
from .models import UserProfile
from .serializers import MeSerializer


def serialize_me(user: User, profile: UserProfile) -> dict[str, object]:
    usage = quota.current(user)
    subscription = plans.current_subscription(user)
    return MeSerializer(
        {
            "id": user.pk,
            "email": user.email,
            "name": user.get_full_name() or None,
            "plan": plans.plan_for(profile),
            "role": profile.role,
            "is_demo": profile.is_demo,
            "usage": {"used": usage.used, "limit": usage.limit, "resets_at": usage.resets_at},
            "subscription": (
                {
                    "status": subscription.status,
                    "current_period_end": subscription.current_period_end,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                }
                if subscription
                else None
            ),
            "email_opt_in": profile.email_opt_in,
            "timezone": profile.timezone,
            "demo_expires_at": profile.demo_expires_at,
        }
    ).data
