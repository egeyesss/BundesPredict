from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from anymail.exceptions import AnymailError
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts import plans
from notifications.matchday import (
    CONTACT_EMAIL,
    Matchday,
    Recipient,
    build_matchday,
    render_matchday_email,
)
from notifications.models import EmailSend
from notifications.tokens import unsubscribe_token

# Resend allows two requests a second by default.
DEFAULT_DELAY_SECONDS = 0.6


class Command(BaseCommand):
    help = "Email the coming matchday's odds to opted-in Pro users, once per matchday."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--now", help="ISO timestamp to use instead of the clock.")
        parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
        parser.add_argument(
            "--recipient",
            help="Send one copy to this address, ignoring plan and opt-in, recording nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        now = self._now(options["now"])
        matchday = build_matchday(now)
        if matchday is None:
            self.stdout.write("no matchday kicks off in the next five days, nothing sent")
            return

        if options["recipient"]:
            users = User.objects.filter(email__iexact=options["recipient"], is_active=True)
            if not users:
                raise CommandError(f"no active user has the address {options['recipient']}")
            for user in users:
                self._send(user, matchday)
            self.stdout.write(f"sent {len(users)} test message to {options['recipient']}")
            return

        sent = skipped = 0
        failed: list[str] = []
        for user in self._eligible(now):
            if EmailSend.objects.filter(user=user, campaign=matchday.campaign).exists():
                skipped += 1
                continue
            try:
                self._send_once(user, matchday)
            except (AnymailError, OSError) as error:
                failed.append(f"{user.email}: {error}")
                continue
            sent += 1
            if options["delay"]:
                time.sleep(options["delay"])

        self.stdout.write(
            f"{matchday.campaign}: sent {sent}, already sent {skipped}, failed {len(failed)}"
        )
        if failed:
            raise CommandError(
                f"{len(failed)} of {sent + len(failed)} sends failed: " + "; ".join(failed)
            )

    @staticmethod
    def _now(raw: str | None) -> datetime:
        if raw is None:
            return timezone.now()
        parsed = parse_datetime(raw)
        if parsed is None or parsed.tzinfo is None:
            raise CommandError("--now must be an ISO timestamp with a UTC offset")
        return parsed

    @staticmethod
    def _eligible(now: datetime) -> list[User]:
        candidates: QuerySet[User] = (
            User.objects.filter(is_active=True, profile__email_opt_in=True, profile__is_demo=False)
            .exclude(email="")
            .select_related("profile")
            .order_by("pk")
        )
        return [user for user in candidates if plans.has_pro(user, now)]

    def _send_once(self, user: User, matchday: Matchday) -> None:
        """Claim the (user, campaign) row first, so two overlapping runs cannot both send."""
        with transaction.atomic():
            claim, created = EmailSend.objects.get_or_create(user=user, campaign=matchday.campaign)
            if not created:
                return
            claim.message_id = self._send(user, matchday)
            claim.save(update_fields=["message_id"])

    def _send(self, user: User, matchday: Matchday) -> str:
        profile = user.profile
        recipient = Recipient(
            first_name=user.first_name,
            timezone=profile.timezone,
            timezone_source=profile.timezone_source,
            token=unsubscribe_token(user.pk),
        )
        rendered = render_matchday_email(matchday, recipient)
        message = EmailMultiAlternatives(
            subject=rendered.subject,
            body=rendered.text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[CONTACT_EMAIL],
            headers={
                "List-Unsubscribe": f"<{rendered.one_click_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        )
        message.attach_alternative(rendered.html, "text/html")
        if not message.send():
            raise OSError(f"the mailer did not accept the message for {user.email}")
        status = getattr(message, "anymail_status", None)
        return str(status.message_id or "") if status is not None else ""
