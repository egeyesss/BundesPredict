from __future__ import annotations

from typing import Any

from rest_framework import serializers

PERIOD_KINDS = ("live", "backtest")


class MetricSummarySerializer(serializers.Serializer[dict[str, Any]]):
    n_fixtures = serializers.IntegerField()
    rps = serializers.FloatField(help_text="Ranked probability score, lower is better.")
    log_loss = serializers.FloatField()
    hit_rate = serializers.FloatField(help_text="Share of fixtures whose top pick won, in [0, 1].")


class TrackRecordPeriodSerializer(serializers.Serializer[dict[str, Any]]):
    kind = serializers.ChoiceField(choices=PERIOD_KINDS)
    label = serializers.CharField(  # type: ignore[assignment]
        help_text='For example "Live since 2026-08-28".'
    )
    since = serializers.DateField(allow_null=True)
    model = MetricSummarySerializer(allow_null=True)
    bookmaker = MetricSummarySerializer(
        allow_null=True, help_text="Bookmaker closing odds over the same fixtures."
    )
    home_win_baseline = MetricSummarySerializer(
        allow_null=True, help_text="A naive model that always backs the home side."
    )


class MatchdayRowSerializer(serializers.Serializer[dict[str, Any]]):
    season = serializers.CharField()
    matchday = serializers.IntegerField()
    n_fixtures = serializers.IntegerField()
    n_resolved = serializers.IntegerField()
    rps = serializers.FloatField(allow_null=True)
    log_loss = serializers.FloatField(allow_null=True)
    hit_rate = serializers.FloatField(allow_null=True)


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
    season = serializers.CharField(required=False)
