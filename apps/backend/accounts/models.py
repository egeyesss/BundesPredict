from __future__ import annotations

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        USER = "user"
        ADMIN = "admin"

    class TimezoneSource(models.TextChoices):
        BROWSER = "browser"
        MANUAL = "manual"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    is_demo = models.BooleanField(default=False)
    demo_expires_at = models.DateTimeField(null=True, blank=True)
    email_opt_in = models.BooleanField(default=True)
    timezone = models.CharField(max_length=64, null=True, blank=True)
    timezone_source = models.CharField(
        max_length=10, choices=TimezoneSource.choices, default=TimezoneSource.BROWSER
    )

    def __str__(self) -> str:
        return f"profile of user {self.user_id}"


class DailyUsage(models.Model):
    """Chats spent by a user on one UTC day; written only through `accounts.quota`."""

    pk = models.CompositePrimaryKey("user", "day")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField()
    chats_used = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.user_id} {self.day}: {self.chats_used}"
