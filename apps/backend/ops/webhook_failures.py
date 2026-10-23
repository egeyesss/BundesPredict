from __future__ import annotations

from django.db.models import F

from .models import WebhookFailure

ERROR_MAX_LENGTH = 500


def record(event_id: str, event_type: str, livemode: bool, error: BaseException) -> None:
    """Keep the latest error for an event; a Stripe retry of the same event bumps `attempts`."""
    message = f"{type(error).__name__}: {error}"[:ERROR_MAX_LENGTH]
    updated = WebhookFailure.objects.filter(event_id=event_id).update(
        error=message, attempts=F("attempts") + 1
    )
    if not updated:
        WebhookFailure.objects.create(
            event_id=event_id, type=event_type, livemode=livemode, error=message
        )
