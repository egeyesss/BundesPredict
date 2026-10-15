"""The `predictions` audit table, adopted in place."""

from __future__ import annotations

from django.db import models

from football.fields import DB_NOW, PlainJSONField
from football.models import ModelRun, Team


class Prediction(models.Model):
    """One agent answer, kept so every response can be audited.

    The `base_*` columns hold the pre-adjustment baseline; `adjustments_json` holds the applied,
    clamped adjustments. `model_run` ties the answer to the exact parameters that produced it.
    """

    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(db_default=DB_NOW)
    model_run = models.ForeignKey(
        ModelRun, on_delete=models.DO_NOTHING, db_index=False, related_name="predictions"
    )
    home = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="home_predictions"
    )
    away = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="away_predictions"
    )
    match_date = models.DateField(null=True, blank=True)
    query = models.CharField(max_length=None, null=True, blank=True)

    p_home = models.FloatField()
    p_draw = models.FloatField()
    p_away = models.FloatField()
    exp_home_goals = models.FloatField()
    exp_away_goals = models.FloatField()

    base_p_home = models.FloatField()
    base_p_draw = models.FloatField()
    base_p_away = models.FloatField()

    adjustments_json = PlainJSONField(default=list)
    explanation = models.CharField(max_length=None, null=True, blank=True)

    class Meta:
        db_table = "predictions"
        indexes = [
            models.Index(fields=["away"], name="ix_predictions_away_id"),
            models.Index(fields=["home"], name="ix_predictions_home_id"),
            models.Index(fields=["model_run"], name="ix_predictions_model_run_id"),
        ]

    def __str__(self) -> str:
        return f"prediction {self.pk}"
