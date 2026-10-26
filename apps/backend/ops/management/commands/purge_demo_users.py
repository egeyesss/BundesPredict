from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from ops.demo import purge_expired


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


class Command(BaseCommand):
    help = "Delete demo users whose 24h are up, with their chats, predictions and sessions."

    def handle(self, *args: Any, **options: Any) -> None:
        report = purge_expired()

        self.stdout.write(
            f"purged {_plural(report.users, 'demo user')} "
            f"({_plural(report.conversations, 'conversation')}, "
            f"{_plural(report.predictions, 'prediction')}, "
            f"{_plural(report.sessions, 'expired session')}); "
            f"{_plural(report.counters, 'old start counter')} removed"
        )
