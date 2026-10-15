import django.db.models.deletion
import django.db.models.expressions
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("football", "0004_fill_team_codes"),
    ]

    operations = [
        migrations.CreateModel(
            name="FixturePrediction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("p_home", models.FloatField()),
                ("p_draw", models.FloatField()),
                ("p_away", models.FloatField()),
                ("exp_home_goals", models.FloatField()),
                ("exp_away_goals", models.FloatField()),
                (
                    "score_grid",
                    models.JSONField(
                        help_text=(
                            "Joint scoreline distribution P(home goals = i, away goals = j) as a "
                            "list of rows: score_grid[i][j] with i = home goals and j = away "
                            "goals, both 0 to 10 (an 11 x 11 grid, truncated at 10 goals and "
                            "renormalized to sum to 1). p_home is the mass below the diagonal "
                            "(i > j), p_draw the diagonal and p_away the mass above it."
                        )
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        help_text=(
                            "The instant the prediction was frozen. Compare with "
                            "fixture.kickoff_utc to prove it was made before kickoff."
                        )
                    ),
                ),
                (
                    "fixture",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="frozen_prediction",
                        to="football.fixture",
                    ),
                ),
                (
                    "model_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="frozen_predictions",
                        to="football.modelrun",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("p_away__gte", 0), ("p_draw__gte", 0), ("p_home__gte", 0)
                        ),
                        name="track_record_probabilities_not_negative",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "p_home__gte",
                                django.db.models.expressions.CombinedExpression(
                                    django.db.models.expressions.CombinedExpression(
                                        models.Value(0.999999), "-", models.F("p_draw")
                                    ),
                                    "-",
                                    models.F("p_away"),
                                ),
                            ),
                            (
                                "p_home__lte",
                                django.db.models.expressions.CombinedExpression(
                                    django.db.models.expressions.CombinedExpression(
                                        models.Value(1.000001), "-", models.F("p_draw")
                                    ),
                                    "-",
                                    models.F("p_away"),
                                ),
                            ),
                        ),
                        name="track_record_probabilities_sum_to_one",
                    ),
                ],
            },
        ),
    ]
