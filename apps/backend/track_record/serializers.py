from __future__ import annotations

from typing import Any

from rest_framework import serializers

PERIOD_KINDS = ("live", "backtest")
OUTCOME_LETTERS = ("H", "D", "A")


class MetricSummarySerializer(serializers.Serializer[dict[str, Any]]):
    n_fixtures = serializers.IntegerField()
    rps = serializers.FloatField(help_text="Ranked probability score, lower is better.")
    log_loss = serializers.FloatField()
    hit_rate = serializers.FloatField(
        allow_null=True,
        help_text="Share of fixtures whose top pick won, in [0, 1]; null if not recorded.",
    )


class ForecasterSerializer(serializers.Serializer[dict[str, Any]]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    kind = serializers.ChoiceField(choices=("model", "market"))
    rps = serializers.FloatField()
    log_loss = serializers.FloatField()
    serving = serializers.BooleanField(help_text="True for the model that serves predictions.")


class TrackRecordPeriodSerializer(serializers.Serializer[dict[str, Any]]):
    kind = serializers.ChoiceField(choices=PERIOD_KINDS)
    label = serializers.CharField(  # type: ignore[assignment]
        help_text='For example "Live since 2026-08-28".'
    )
    since = serializers.DateField(allow_null=True)
    model = MetricSummarySerializer(allow_null=True)
    bookmaker = MetricSummarySerializer(
        allow_null=True,
        help_text="Bookmaker closing odds over the fixtures that have them.",
    )
    base_rate = MetricSummarySerializer(
        allow_null=True,
        help_text="The league's long-run 44% home, 25% draw, 31% away split as a forecast.",
    )
    calibration_error = serializers.FloatField(
        allow_null=True, help_text="Expected calibration error of the model; backtest only."
    )
    forecasters = ForecasterSerializer(
        many=True, help_text="Every forecaster scored in the backtest; empty for the live record."
    )


class TeamRefSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField()
    code = serializers.CharField(allow_null=True)


class ResolvedFixtureSerializer(serializers.Serializer[dict[str, Any]]):
    fixture_id = serializers.IntegerField()
    kickoff_utc = serializers.DateTimeField()
    home = TeamRefSerializer()
    away = TeamRefSerializer()
    home_goals = serializers.IntegerField()
    away_goals = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=OUTCOME_LETTERS)
    p_home = serializers.FloatField()
    p_draw = serializers.FloatField()
    p_away = serializers.FloatField()
    rps = serializers.FloatField()
    hit = serializers.BooleanField()


class MatchdayRowSerializer(serializers.Serializer[dict[str, Any]]):
    season = serializers.CharField()
    matchday = serializers.IntegerField()
    n_fixtures = serializers.IntegerField(help_text="Frozen predictions on this matchday.")
    n_resolved = serializers.IntegerField()
    rps = serializers.FloatField(allow_null=True)
    log_loss = serializers.FloatField(allow_null=True)
    hit_rate = serializers.FloatField(allow_null=True)
    bookmaker_rps = serializers.FloatField(allow_null=True)
    base_rate_rps = serializers.FloatField(allow_null=True)
    fixtures = ResolvedFixtureSerializer(many=True, help_text="Resolved fixtures, kickoff order.")


class CalibrationBinSerializer(serializers.Serializer[dict[str, Any]]):
    lower = serializers.FloatField()
    upper = serializers.FloatField()
    predicted_mean = serializers.FloatField()
    observed_rate = serializers.FloatField()
    count = serializers.IntegerField()


class TrackRecordSerializer(serializers.Serializer[dict[str, Any]]):
    season = serializers.CharField(allow_null=True, help_text="The requested season, if any.")
    live = TrackRecordPeriodSerializer()
    backtest = TrackRecordPeriodSerializer()
    matchdays = MatchdayRowSerializer(many=True, help_text="Live matchdays, newest first.")
    calibration = CalibrationBinSerializer(
        many=True, help_text="Live predictions, home/draw/away pooled into probability bins."
    )


class TrackRecordQuerySerializer(serializers.Serializer[dict[str, Any]]):
    season = serializers.CharField(
        required=False, help_text="Season code such as 2627; defaults to the newest."
    )
