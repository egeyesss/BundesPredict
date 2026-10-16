"""Teams, fixtures and the market distributions shared with the agent's responses."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from bundespredict.agent.tools import markets_to_dict
from bundespredict.model.markets import Markets

FIXTURE_SCOPES = ("next_matchday", "week")


class TeamSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    short_name = serializers.CharField()
    code = serializers.CharField(help_text="Three-letter club code; keys the crest set.")
    crest = serializers.CharField(
        allow_null=True, help_text='Site-relative path such as "/crests/BVB.svg".'
    )


class ScoreSerializer(serializers.Serializer[dict[str, Any]]):
    home = serializers.IntegerField()
    away = serializers.IntegerField()
    p = serializers.FloatField()


class MarketsSerializer(serializers.Serializer[dict[str, Any]]):
    p_home = serializers.FloatField()
    p_draw = serializers.FloatField()
    p_away = serializers.FloatField()
    p_over_2_5 = serializers.FloatField()
    p_under_2_5 = serializers.FloatField()
    p_btts = serializers.FloatField()
    exp_home_goals = serializers.FloatField()
    exp_away_goals = serializers.FloatField()
    top_scores = ScoreSerializer(many=True)
    score_grid = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        help_text="Scoreline distribution, rows are home goals and columns are away goals.",
    )


class BaseProbabilitiesSerializer(serializers.Serializer[dict[str, Any]]):
    p_home = serializers.FloatField()
    p_draw = serializers.FloatField()
    p_away = serializers.FloatField()
    exp_home_goals = serializers.FloatField()
    exp_away_goals = serializers.FloatField()


class FixtureCardSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    season = serializers.CharField()
    matchday = serializers.IntegerField()
    kickoff_utc = serializers.DateTimeField()
    home = TeamSerializer()
    away = TeamSerializer()
    base = BaseProbabilitiesSerializer()
    model_run_id = serializers.IntegerField()


class FixtureDetailSerializer(FixtureCardSerializer):
    markets = MarketsSerializer()


class FixtureListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    scope = serializers.ChoiceField(choices=FIXTURE_SCOPES, default="next_matchday")


def markets_payload(markets: Markets) -> dict[str, Any]:
    """The `Markets` fields the API exposes, rounded the way the agent's tool results are."""
    grid = [[round(p, 6) for p in row] for row in markets.score_grid]
    return {**markets_to_dict(markets), "score_grid": grid}
