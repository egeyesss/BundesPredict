"""Turns verified webhook events into Subscription rows.

Payload order is not trusted: each relevant event only names a subscription, and the row is
rewritten from a fresh fetch, so a late `updated` and an early `created` converge on one state.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe
from django.contrib.auth.models import User
from django.db import transaction

from . import stripe_api
from .models import StripeCustomer, StripeEvent, Subscription

logger = logging.getLogger(__name__)

SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}
INVOICE_EVENTS = {"invoice.paid", "invoice.payment_failed"}


def sync_subscription(livemode: bool, subscription_id: str) -> Subscription | None:
    """Upsert the row from Stripe; None when the subscription's customer is not one of ours."""
    snapshot = stripe_api.fetch_subscription(livemode, subscription_id)
    customer = StripeCustomer.objects.filter(
        customer_id=snapshot.customer_id, livemode=livemode
    ).first()
    if customer is None:
        logger.warning("subscription %s belongs to an unknown customer", subscription_id)
        return None
    subscription, _ = Subscription.objects.update_or_create(
        subscription_id=snapshot.id,
        defaults={
            "customer": customer,
            "livemode": livemode,
            "status": snapshot.status,
            "current_period_end": snapshot.current_period_end,
            "cancel_at_period_end": snapshot.cancel_at_period_end,
        },
    )
    return subscription


def _subscription_id_of_invoice(invoice: dict[str, Any]) -> str | None:
    details = (invoice.get("parent") or {}).get("subscription_details") or {}
    found = details.get("subscription") or invoice.get("subscription")
    if isinstance(found, dict):
        found = found.get("id")
    return found or None


def _link_checkout_customer(session: dict[str, Any], livemode: bool) -> None:
    reference, customer_id = session.get("client_reference_id"), session.get("customer")
    if not reference or not customer_id:
        return
    user = User.objects.filter(pk=int(reference)).first()
    if user is not None:
        StripeCustomer.objects.get_or_create(
            user=user, livemode=livemode, defaults={"customer_id": customer_id}
        )


def _process(event: stripe.Event, livemode: bool) -> None:
    obj: dict[str, Any] = event.data.object.to_dict()
    subscription_id: str | None = None
    if event.type in SUBSCRIPTION_EVENTS:
        subscription_id = obj["id"]
    elif event.type == "checkout.session.completed":
        _link_checkout_customer(obj, livemode)
        subscription_id = obj.get("subscription")
    elif event.type in INVOICE_EVENTS:
        subscription_id = _subscription_id_of_invoice(obj)
    if subscription_id:
        sync_subscription(livemode, subscription_id)


def handle_event(event: stripe.Event, livemode: bool) -> bool:
    """Record and process an event once; False when the id was already handled.

    The event row and the sync share a transaction, so a failed sync rolls the row back and
    Stripe's retry runs it again.
    """
    with transaction.atomic():
        _, created = StripeEvent.objects.get_or_create(
            event_id=event.id, defaults={"type": event.type, "livemode": livemode}
        )
        if not created:
            return False
        _process(event, livemode)
    return True
