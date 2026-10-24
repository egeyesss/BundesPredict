from __future__ import annotations

from django.contrib import admin

from football.admin import ReadOnlyAdmin

from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "created_at",
        "user",
        "home",
        "away",
        "p_home",
        "p_draw",
        "p_away",
        "cost_usd",
        "model_run",
    )
    list_filter = ("model_run", "created_at")
    list_select_related = ("home", "away", "model_run", "user")
    search_fields = ("query", "home__name", "away__name", "user__email")
    ordering = ("-created_at", "-id")
    date_hierarchy = "created_at"
