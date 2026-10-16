from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    if created:
        UserProfile.objects.get_or_create(user=instance)
