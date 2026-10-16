from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from .models import UserProfile

FREE_DAILY_LIMIT = 3


def limit_for(user: AbstractBaseUser) -> int:
    """Chats per UTC day for this user; a fixed free limit until billing supplies plans."""
    return FREE_DAILY_LIMIT


def plan_for(profile: UserProfile) -> str:
    return "demo" if profile.is_demo else "free"
