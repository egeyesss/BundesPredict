"""Race-safe daily chat quota.

`consume` is one INSERT ... ON CONFLICT statement, so two concurrent requests at `limit - 1`
serialize on the row lock and exactly one of them passes the `WHERE` clause.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.db import connection
from django.utils import timezone

from . import plans

_CONSUME_SQL = """
INSERT INTO accounts_dailyusage (user_id, day, chats_used) VALUES (%s, %s, 1)
ON CONFLICT (user_id, day) DO UPDATE SET chats_used = accounts_dailyusage.chats_used + 1
WHERE accounts_dailyusage.chats_used < %s
RETURNING chats_used
"""

_REFUND_SQL = """
UPDATE accounts_dailyusage SET chats_used = GREATEST(chats_used - 1, 0)
WHERE user_id = %s AND day = %s
"""

_CURRENT_SQL = "SELECT chats_used FROM accounts_dailyusage WHERE user_id = %s AND day = %s"


@dataclass(frozen=True)
class Usage:
    used: int
    limit: int
    resets_at: datetime


def _utc_day(now: datetime | None) -> date:
    return (now or timezone.now()).astimezone(UTC).date()


def _next_reset(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)


def consume(user: AbstractBaseUser, now: datetime | None = None) -> Usage | None:
    """Spend one chat for today (UTC); None when the user is already at the limit."""
    limit = plans.limit_for(user)
    if limit <= 0:
        return None
    day = _utc_day(now)
    with connection.cursor() as cursor:
        cursor.execute(_CONSUME_SQL, [user.pk, day, limit])
        row = cursor.fetchone()
    if row is None:
        return None
    return Usage(used=row[0], limit=limit, resets_at=_next_reset(day))


def refund(user: AbstractBaseUser, now: datetime | None = None) -> None:
    """Give a chat back after a request failed before any tokens were spent."""
    with connection.cursor() as cursor:
        cursor.execute(_REFUND_SQL, [user.pk, _utc_day(now)])


def current(user: AbstractBaseUser, now: datetime | None = None) -> Usage:
    day = _utc_day(now)
    with connection.cursor() as cursor:
        cursor.execute(_CURRENT_SQL, [user.pk, day])
        row = cursor.fetchone()
    return Usage(used=row[0] if row else 0, limit=plans.limit_for(user), resets_at=_next_reset(day))
