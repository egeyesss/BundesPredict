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


class WebhookEventSerializer(WebhookFailureSerializer):
    status = serializers.ChoiceField(choices=("processed", "failed"))
    error = serializers.CharField(allow_blank=True)


class FailedPaymentSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.CharField(help_text="Masked for demo viewers.")
    livemode = serializers.BooleanField()
    amount_cents = serializers.IntegerField()
    failed_at = serializers.DateTimeField()


class ModeSummarySerializer(serializers.Serializer[dict[str, Any]]):
    active_subscribers = serializers.IntegerField()
    mrr_cents = serializers.IntegerField()


class ProUserCostSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.CharField(help_text="Masked for demo viewers.")
    cost_cents = serializers.IntegerField(help_text="Agent spend over the last 30 days.")


class AdminMetricsSerializer(serializers.Serializer[dict[str, Any]]):
    generated_at = serializers.DateTimeField()
    masked = serializers.BooleanField(help_text="True when emails are masked for a demo viewer.")
    active_subscribers = serializers.IntegerField()
    mrr_cents = serializers.IntegerField(help_text="Live-mode subscriptions only.")
    test_mode = ModeSummarySerializer(
        help_text="The same two numbers for test-mode subscriptions; never added to the live ones."
    )
    signups_7d = serializers.IntegerField()
    signups_30d = serializers.IntegerField()
    monthly_churn = serializers.FloatField(help_text="Share of subscribers lost in 30 days.")
    chats_per_day = ChatsPerDaySerializer(many=True)
    llm_cost_per_user_cents = serializers.FloatField(
        help_text="Mean agent spend over 30 days per user who asked the agent anything."
    )
    cost_to_revenue_per_pro_user = serializers.FloatField(
        allow_null=True,
        help_text="Pro users' agent spend over their net revenue; null with no Pro users.",
    )
    pro_user_costs = ProUserCostSerializer(many=True, help_text="The ten heaviest Pro users.")
    webhook_failures = WebhookFailureSerializer(
        many=True, help_text="Events whose sync failed and that Stripe has not redelivered yet."
    )
    webhook_events = WebhookEventSerializer(
        many=True, help_text="Newest first, failed or processed."
    )
    failed_payments = FailedPaymentSerializer(many=True)
