from __future__ import annotations

from typing import Any

from rest_framework import serializers


class ChatsPerDaySerializer(serializers.Serializer[dict[str, Any]]):
    day = serializers.DateField()
    free = serializers.IntegerField()
    pro = serializers.IntegerField()
    demo = serializers.IntegerField()


class WebhookFailureSerializer(serializers.Serializer[dict[str, Any]]):
    event_id = serializers.CharField()
    type = serializers.CharField()
    livemode = serializers.BooleanField()
    error = serializers.CharField()
    received_at = serializers.DateTimeField()


class FailedPaymentSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.CharField(help_text="Masked for demo viewers.")
    amount_cents = serializers.IntegerField()
    failed_at = serializers.DateTimeField()


class AdminMetricsSerializer(serializers.Serializer[dict[str, Any]]):
    generated_at = serializers.DateTimeField()
    masked = serializers.BooleanField(help_text="True when emails are masked for a demo viewer.")
    active_subscribers = serializers.IntegerField()
    mrr_cents = serializers.IntegerField(help_text="Live-mode subscriptions only.")
    signups_7d = serializers.IntegerField()
    signups_30d = serializers.IntegerField()
    monthly_churn = serializers.FloatField(help_text="Share of subscribers lost in 30 days.")
    chats_per_day = ChatsPerDaySerializer(many=True)
    llm_cost_per_user_cents = serializers.FloatField()
    cost_to_revenue_per_pro_user = serializers.FloatField(allow_null=True)
    webhook_failures = WebhookFailureSerializer(many=True)
    failed_payments = FailedPaymentSerializer(many=True)
