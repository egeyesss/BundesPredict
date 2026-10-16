"""Small helpers shared by the commands. The leading underscore keeps Django from listing it."""

from __future__ import annotations

from datetime import UTC, date, datetime


def today_utc() -> date:
    return datetime.now(UTC).date()
