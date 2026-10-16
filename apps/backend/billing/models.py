from __future__ import annotations

from django.conf import settings
from django.db import models


class StripeCustomer(models.Model):
    """A user's Stripe customer; test and live mode each get their own."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stripe_customers"
    )
    livemode = models.BooleanField()
    customer_id = models.CharField(max_length=255, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "livemode"], name="one_customer_per_mode")
        ]

    def __str__(self) -> str:
        return self.customer_id


class Subscription(models.Model):
    """A mirror of a Stripe subscription, written only from a re-fetch inside a webhook."""

    customer = models.ForeignKey(
        StripeCustomer, on_delete=models.CASCADE, related_name="subscriptions"
    )
    subscription_id = models.CharField(max_length=255, unique=True)
    livemode = models.BooleanField()
    status = models.CharField(max_length=32)
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.subscription_id} ({self.status})"


class StripeEvent(models.Model):
    """Every webhook event id already handled; the primary key is the idempotency guard."""

    event_id = models.CharField(max_length=255, primary_key=True)
    type = models.CharField(max_length=100)
    livemode = models.BooleanField()
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.event_id} ({self.type})"
