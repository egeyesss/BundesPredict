"""Throwaway demo accounts: creation with start limits, and the purge that removes them."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import UserProfile
from chat.models import Conversation
from predictions.models import Prediction

from .demo_seed import seed_conversations
from .models import DemoStartCount

DEMO_LIFETIME = timedelta(hours=24)
DEMO_STARTS_PER_IP_PER_DAY = 3
DEMO_STARTS_PER_DAY = 25
DEMO_EMAIL_DOMAIN = "demo.bundespredict.invalid"
SITE_SCOPE = "site"
COUNTER_RETENTION = timedelta(days=2)

IP_LIMIT_CODE = "demo_ip_limit"
BUDGET_CODE = "demo_budget"

_SPEND_SQL = """
INSERT INTO ops_demostartcount (scope, day, starts) VALUES (%s, %s, 1)
ON CONFLICT (scope, day) DO UPDATE SET starts = ops_demostartcount.starts + 1
WHERE ops_demostartcount.starts < %s
RETURNING starts
"""


class DemoLimitReached(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _ip_scope(client_ip: str) -> str:
    digest = hmac.new(settings.SECRET_KEY.encode(), f"demo-ip:{client_ip}".encode(), sha256)
    return f"ip:{digest.hexdigest()}"


def _spend(scope: str, day: date, limit: int) -> bool:
    """One statement, so concurrent starts serialize on the counter row and none overshoots."""
    with connection.cursor() as cursor:
        cursor.execute(_SPEND_SQL, [scope, day, limit])
        return cursor.fetchone() is not None


def start_demo(*, client_ip: str | None, now: datetime | None = None) -> User:
    """Creates a seeded demo user, counting the start against the address and the site.

    The counters, the user and the seeded chats share one transaction, so a refused or failed
    start leaves the budget as it was. A start without an address is limited by the site budget
    alone.
    """
    now = now or timezone.now()
    day = now.astimezone(UTC).date()
    with transaction.atomic():
        if client_ip and not _spend(_ip_scope(client_ip), day, DEMO_STARTS_PER_IP_PER_DAY):
            raise DemoLimitReached(
                IP_LIMIT_CODE,
                f"You have already started {DEMO_STARTS_PER_IP_PER_DAY} demos today. "
                "Try again tomorrow or sign up for a free account.",
            )
        if not _spend(SITE_SCOPE, day, DEMO_STARTS_PER_DAY):
            raise DemoLimitReached(
                BUDGET_CODE,
                "The demo has reached its limit for today. Try again tomorrow or sign up "
                "for a free account.",
            )
        user = _create_user(now)
        seed_conversations(user, now=now)
    return user


def _create_user(now: datetime) -> User:
    handle = secrets.token_hex(8)
    user = User.objects.create_user(
        username=f"demo-{handle}", email=f"demo-{handle}@{DEMO_EMAIL_DOMAIN}", password=None
    )
    UserProfile.objects.filter(user=user).update(is_demo=True, demo_expires_at=now + DEMO_LIFETIME)
    user.refresh_from_db()
    return user


@dataclass(frozen=True)
class PurgeReport:
    users: int
    conversations: int
    predictions: int
    sessions: int
    counters: int


def _session_keys_of(user_ids: set[int]) -> list[str]:
    keys = []
    for session in Session.objects.iterator():
        raw_id = session.get_decoded().get("_auth_user_id")
        if raw_id is not None and int(raw_id) in user_ids:
            keys.append(session.session_key)
    return keys


def purge_expired(now: datetime | None = None) -> PurgeReport:
    """Deletes expired demo users and every row tied to them, plus start counters past retention.

    Predictions go first because `Prediction.user` is SET_NULL: left to the cascade they would
    survive as ownerless rows and be counted as real chats.
    """
    now = now or timezone.now()
    expired_ids = set(
        User.objects.filter(profile__is_demo=True, profile__demo_expires_at__lt=now).values_list(
            "pk", flat=True
        )
    )
    with transaction.atomic():
        conversations = Conversation.objects.filter(user_id__in=expired_ids).count()
        predictions, _ = Prediction.objects.filter(user_id__in=expired_ids).delete()
        session_keys = _session_keys_of(expired_ids) if expired_ids else []
        Session.objects.filter(session_key__in=session_keys).delete()
        User.objects.filter(pk__in=expired_ids).delete()
        counters, _ = DemoStartCount.objects.filter(
            day__lt=now.astimezone(UTC).date() - COUNTER_RETENTION
        ).delete()
    return PurgeReport(
        users=len(expired_ids),
        conversations=conversations,
        predictions=predictions,
        sessions=len(session_keys),
        counters=counters,
    )
