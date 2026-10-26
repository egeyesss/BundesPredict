from __future__ import annotations

from django.db import models


class WebhookFailure(models.Model):
    """The last error a Stripe event hit; the event's own row is rolled back when its sync fails."""

    event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=100)
    livemode = models.BooleanField()
    error = models.TextField()
    attempts = models.PositiveIntegerField(default=1)
    last_failed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_failed_at"]

    def __str__(self) -> str:
        return f"{self.event_id} ({self.type})"


class DemoStartCount(models.Model):
    """Demo starts per UTC day for one hashed client address, or for the whole site."""

    scope = models.CharField(max_length=80)
    day = models.DateField()
    starts = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["scope", "day"], name="one_count_per_day")]

    def __str__(self) -> str:
        return f"{self.scope[:12]} {self.day}: {self.starts}"
