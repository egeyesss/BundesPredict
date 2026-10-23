from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailSend(models.Model):
    """One row per user and campaign; the unique pair is what makes a re-run send nothing."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_sends"
    )
    campaign = models.CharField(max_length=100, help_text="For example matchday-2627-06.")
    sent_at = models.DateTimeField(default=timezone.now)
    message_id = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "campaign"], name="one_email_per_user_and_campaign"
            )
        ]

    def __str__(self) -> str:
        return f"{self.campaign} to user {self.user_id}"
