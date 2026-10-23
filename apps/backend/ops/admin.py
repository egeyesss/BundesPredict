from __future__ import annotations

from django.contrib import admin

from football.admin import ReadOnlyAdmin

from .models import WebhookFailure


@admin.register(WebhookFailure)
class WebhookFailureAdmin(ReadOnlyAdmin):
    list_display = ("event_id", "type", "livemode", "attempts", "last_failed_at")
    list_filter = ("livemode", "type")
    search_fields = ("event_id", "error")
