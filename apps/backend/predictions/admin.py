from __future__ import annotations

from django.contrib import admin

from football.admin import ReadOnlyAdmin

from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(ReadOnlyAdmin):
    list_display = ("id", "created_at", "home", "away", "p_home", "p_draw", "p_away", "model_run")
    list_select_related = ("home", "away", "model_run")
    search_fields = ("query", "home__name", "away__name")
    ordering = ("-created_at", "-id")
