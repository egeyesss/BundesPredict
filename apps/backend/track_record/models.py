from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models import F, Q


class FixturePrediction(models.Model):
    """The base model's prediction for one fixture, frozen before kickoff.

    Rows are written once by `snapshot_predictions` and never changed, so the track record can
    prove what the model said before the match. Only the base model is stored; the agent's
    adjustments are not scored on accuracy.
    """

    fixture = models.OneToOneField(
        "football.Fixture", on_delete=models.PROTECT, related_name="frozen_prediction"
    )
    model_run = models.ForeignKey(
        "football.ModelRun", on_delete=models.PROTECT, related_name="frozen_predictions"
    )
    p_home = models.FloatField()
    p_draw = models.FloatField()
    p_away = models.FloatField()
    exp_home_goals = models.FloatField()
    exp_away_goals = models.FloatField()
    score_grid = models.JSONField(
        help_text=(
            "Joint scoreline distribution P(home goals = i, away goals = j) as a list of rows: "
            "score_grid[i][j] with i = home goals and j = away goals, both 0 to 10 (an 11 x 11 "
            "grid, truncated at 10 goals and renormalized to sum to 1). p_home is the mass "
            "below the diagonal (i > j), p_draw the diagonal and p_away the mass above it."
        )
    )
    created_at = models.DateTimeField(
        help_text=(
            "The instant the prediction was frozen. Compare with fixture.kickoff_utc to prove "
            "it was made before kickoff."
        )
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(p_home__gte=0, p_draw__gte=0, p_away__gte=0),
                name="track_record_probabilities_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(
                    p_home__gte=0.999999 - F("p_draw") - F("p_away"),
                    p_home__lte=1.000001 - F("p_draw") - F("p_away"),
                ),
                name="track_record_probabilities_sum_to_one",
            ),
        ]

    def __str__(self) -> str:
        return f"fixture {self.fixture_id} frozen with run {self.model_run_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise RuntimeError("a frozen prediction cannot be saved again")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise RuntimeError("a frozen prediction cannot be deleted")


class Resolution(models.Model):
    """The final score of a frozen prediction's fixture, written once the result is in."""

    prediction = models.OneToOneField(
        FixturePrediction, on_delete=models.PROTECT, related_name="resolution"
    )
    home_goals = models.PositiveSmallIntegerField()
    away_goals = models.PositiveSmallIntegerField()
    outcome = models.CharField(max_length=1, choices=[("H", "Home"), ("D", "Draw"), ("A", "Away")])
    resolved_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(outcome="H", home_goals__gt=F("away_goals"))
                    | Q(outcome="D", home_goals=F("away_goals"))
                    | Q(outcome="A", home_goals__lt=F("away_goals"))
                ),
                name="track_record_outcome_matches_score",
            ),
        ]

    def __str__(self) -> str:
        return f"prediction {self.prediction_id} resolved {self.home_goals}-{self.away_goals}"
