from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from billing import clock_check


class Command(BaseCommand):
    help = "Simulate a renewal and a failed payment on a Stripe test clock (test mode only)."

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.STRIPE_SECRET_KEY_TEST or not settings.STRIPE_PRICE_ID_TEST:
            raise CommandError("Set STRIPE_SECRET_KEY_TEST and STRIPE_PRICE_ID_TEST first.")
        try:
            clock_check.run(lambda line: self.stdout.write(line))
        except clock_check.CheckFailed as failure:
            raise CommandError(str(failure)) from failure
