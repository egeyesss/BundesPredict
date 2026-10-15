from __future__ import annotations

from django.contrib import admin

from football.admin import ReadOnlyAdmin

from .models import FixturePrediction


@admin.register(FixturePrediction)
class FixturePredictionAdmin(ReadOnlyAdmin):
    list_display = ("fixture", "p_home", "p_draw", "p_away", "model_run", "created_at")
    list_select_related = ("fixture__home", "fixture__away", "model_run")
    ordering = ("-fixture__kickoff_utc",)
