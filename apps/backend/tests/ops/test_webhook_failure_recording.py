"""A webhook whose sync raises leaves a `WebhookFailure` row for the dashboard."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest
from rest_framework.test import APIClient

from billing import stripe_api
from billing.models import StripeEvent
from ops.models import WebhookFailure

SECRET = "whsec_failure_test"
pytestmark = pytest.mark.django_db


def post_event(client: APIClient, event_id: str) -> Any:
    payload = json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": "customer.subscription.updated",
            "livemode": False,
            "data": {"object": {"id": "sub_1", "object": "subscription"}},
        }
    )
    stamp = int(time.time())
    digest = hmac.new(SECRET.encode(), f"{stamp}.{payload}".encode(), hashlib.sha256)
    return client.post(
        "/stripe/webhook/test",
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={stamp},v1={digest.hexdigest()}",
    )


def test_a_failing_sync_is_recorded_once_per_event_and_counts_attempts(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.STRIPE_WEBHOOK_SECRET_TEST = SECRET

    def explode(livemode: bool, subscription_id: str) -> None:
        raise RuntimeError("stripe timed out")

    monkeypatch.setattr(stripe_api, "fetch_subscription", explode)
    client = APIClient(raise_request_exception=False)

    assert post_event(client, "evt_1").status_code == 500
    assert post_event(client, "evt_1").status_code == 500

    failure = WebhookFailure.objects.get()
    assert (failure.event_id, failure.attempts) == ("evt_1", 2)
    assert failure.error == "RuntimeError: stripe timed out"
    assert not StripeEvent.objects.exists()
