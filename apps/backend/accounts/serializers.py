from __future__ import annotations

import zoneinfo
from typing import Any

from rest_framework import serializers

PLANS = ("free", "pro", "demo")
ROLES = ("user", "admin")


class UsageSerializer(serializers.Serializer[dict[str, Any]]):
    used = serializers.IntegerField()
    limit = serializers.IntegerField()
    resets_at = serializers.DateTimeField()


class SubscriptionSerializer(serializers.Serializer[dict[str, Any]]):
    status = serializers.CharField(help_text="The Stripe subscription status, passed through.")
    current_period_end = serializers.DateTimeField()
    cancel_at_period_end = serializers.BooleanField()


class MeSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField(allow_null=True)
    plan = serializers.ChoiceField(choices=PLANS)
    role = serializers.ChoiceField(choices=ROLES)
    is_demo = serializers.BooleanField()
    usage = UsageSerializer()
    subscription = SubscriptionSerializer(allow_null=True)
    email_opt_in = serializers.BooleanField()
    timezone = serializers.CharField(
        allow_null=True, help_text="IANA name such as America/Toronto; null until reported."
    )


class MeUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    email_opt_in = serializers.BooleanField(required=False)
    timezone = serializers.CharField(required=False, allow_null=True)

    def validate_timezone(self, value: str | None) -> str | None:
        if value is not None and value not in zoneinfo.available_timezones():
            raise serializers.ValidationError("Unknown IANA time zone.")
        return value
