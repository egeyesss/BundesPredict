from __future__ import annotations

from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer

from . import plans, quota
from .models import UserProfile
from .serializers import MeSerializer, MeUpdateSerializer


def _serialize_me(user: User, profile: UserProfile) -> dict[str, object]:
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


def _apply_timezone(profile: UserProfile, timezone: str | None, source: str) -> None:
    """Store the zone unless a manual choice is pinned and this report comes from the browser."""
    if timezone is None:
        profile.timezone = None
        profile.timezone_source = UserProfile.TimezoneSource.BROWSER
    elif source == UserProfile.TimezoneSource.MANUAL:
        profile.timezone = timezone
        profile.timezone_source = UserProfile.TimezoneSource.MANUAL
    elif profile.timezone_source != UserProfile.TimezoneSource.MANUAL:
        profile.timezone = timezone


class MeView(APIView):
    @extend_schema(
        operation_id="me_retrieve",
        tags=["accounts"],
        responses={200: MeSerializer, 401: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response(_serialize_me(user, profile))

    @extend_schema(
        operation_id="me_partial_update",
        tags=["accounts"],
        request=MeUpdateSerializer,
        responses={200: MeSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
        description=(
            "`email_opt_in` and `timezone` are the only writable profile fields; "
            "`timezone_source` says where a reported zone came from."
        ),
    )
    def patch(self, request: Request) -> Response:
        serializer = MeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user: User = request.user  # type: ignore[assignment]
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if "email_opt_in" in data:
            profile.email_opt_in = data["email_opt_in"]
        if "timezone" in data:
            _apply_timezone(profile, data["timezone"], data.get("timezone_source", "browser"))
        profile.save()
        return Response(_serialize_me(user, profile))
