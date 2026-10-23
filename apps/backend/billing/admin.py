from __future__ import annotations

from django.contrib import admin

from football.admin import ReadOnlyAdmin

from .models import StripeCustomer, StripeEvent, Subscription


@admin.register(StripeCustomer)
class StripeCustomerAdmin(ReadOnlyAdmin):
    list_display = ("customer_id", "user", "livemode")
    list_filter = ("livemode",)
    search_fields = ("customer_id", "user__email")
    list_select_related = ("user",)


@admin.register(Subscription)
class SubscriptionAdmin(ReadOnlyAdmin):
    list_display = (
        "subscription_id",
        "customer",
        "status",
        "livemode",
        "current_period_end",
        "cancel_at_period_end",
        "updated_at",
    )
    list_filter = ("status", "livemode", "cancel_at_period_end")
    search_fields = ("subscription_id", "customer__customer_id", "customer__user__email")
    list_select_related = ("customer__user",)
    ordering = ("-updated_at",)


@admin.register(StripeEvent)
class StripeEventAdmin(ReadOnlyAdmin):
    list_display = ("event_id", "type", "livemode", "received_at")
    list_filter = ("livemode", "type")
    search_fields = ("event_id", "type")
    ordering = ("-received_at",)
