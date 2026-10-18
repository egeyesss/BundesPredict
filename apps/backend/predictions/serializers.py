"""Request, response and stream-event shapes for the agent endpoint.

`PredictResponseSerializer` is the agent's answer as the result components read it. The `*Frame`
serializers describe the decoded SSE frames and exist only so the OpenAPI schema carries every
event payload; nothing renders through them.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from accounts.serializers import UsageSerializer
from bundespredict.agent.loop import AgentResult
from bundespredict.agent.tools import _applied_adjustment
from config.api import ErrorSerializer
from football.serializers import MarketsSerializer, markets_payload

QUERY_MAX_LENGTH = 500

# The tools the loop can call. Not an enum in the schema, so a new tool never breaks old clients.
KNOWN_TOOL_NAMES = (
    "predict_match",
    "predict_match_with_context",
    "get_team_form",
    "lookup_player",
    "get_weather",
    "get_recent_results",
    "get_upcoming_fixtures",
)


class PredictRequestSerializer(serializers.Serializer[dict[str, Any]]):
    query = serializers.CharField(min_length=1, max_length=QUERY_MAX_LENGTH)
    conversation_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    fixture_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class AppliedAdjustmentSerializer(serializers.Serializer[dict[str, Any]]):
    factor = serializers.CharField()
    team = serializers.CharField(allow_null=True)
    target = serializers.CharField()
    requested_magnitude_xg = serializers.FloatField()
    effective_magnitude_xg = serializers.FloatField()
    confidence = serializers.CharField()
    rationale = serializers.CharField()


class PredictResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The agent's answer: baseline vs. adjusted, the adjustments, the words."""

    home = serializers.CharField(allow_null=True)
    away = serializers.CharField(allow_null=True)
    explanation = serializers.CharField(allow_blank=True)
    baseline = MarketsSerializer(allow_null=True)
    adjusted = MarketsSerializer(allow_null=True)
    adjustments = AppliedAdjustmentSerializer(many=True)
    prediction_id = serializers.IntegerField(allow_null=True)


def serialize_predict_response(result: AgentResult, prediction_id: int | None) -> dict[str, Any]:
    """The JSON-ready `PredictResponse` for one agent run and its persisted audit row id."""
    record = result.record
    if record is None:
        # The agent answered without predicting a fixture (a clarification, for instance).
        payload: dict[str, Any] = {
            "home": None,
            "away": None,
            "explanation": result.explanation,
            "baseline": None,
            "adjusted": None,
            "adjustments": [],
            "prediction_id": None,
        }
    else:
        payload = {
            "home": record.home,
            "away": record.away,
            "explanation": result.explanation,
            "baseline": markets_payload(record.baseline),
            "adjusted": markets_payload(record.adjusted) if record.adjusted is not None else None,
            "adjustments": [_applied_adjustment(a) for a in record.adjustments],
            "prediction_id": prediction_id,
        }
    return dict(PredictResponseSerializer(payload).data)


class QuotaExceededErrorSerializer(ErrorSerializer):
    """The 402 body: the usual error plus where the user stands and where to upgrade."""

    usage = UsageSerializer()
    upgrade_url = serializers.CharField()


class ConversationEventDataSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(allow_null=True)
    title = serializers.CharField(allow_blank=True)


class ToolCallStageSerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.ChoiceField(choices=["tool_call"])
    name = serializers.CharField(help_text="One of KNOWN_TOOL_NAMES today; treat others as opaque.")
    input = serializers.DictField()


class ToolResultStageSerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.ChoiceField(choices=["tool_result"])
    name = serializers.CharField()
    ok = serializers.BooleanField()
    summary = serializers.CharField(allow_blank=True)


class StreamErrorDataSerializer(ErrorSerializer):
    """Sent in place of `result` when the run fails after the stream has started."""


_stage_data = PolymorphicProxySerializer(
    component_name="StageEventData",
    serializers={
        "tool_call": ToolCallStageSerializer,
        "tool_result": ToolResultStageSerializer,
    },
    resource_type_field_name="type",
)


@extend_schema_field(_stage_data)
class StageDataField(serializers.JSONField):
    pass


# The frame serializers only describe the wire format, so shadowing `Serializer.data` is harmless.
class ConversationFrameSerializer(serializers.Serializer[dict[str, Any]]):
    event = serializers.ChoiceField(choices=["conversation"])
    data = ConversationEventDataSerializer()  # type: ignore[assignment]


class QuotaFrameSerializer(serializers.Serializer[dict[str, Any]]):
    event = serializers.ChoiceField(choices=["quota"])
    data = UsageSerializer()  # type: ignore[assignment]


class StageFrameSerializer(serializers.Serializer[dict[str, Any]]):
    event = serializers.ChoiceField(choices=["stage"])
    data = StageDataField()  # type: ignore[assignment]


class ResultFrameSerializer(serializers.Serializer[dict[str, Any]]):
    event = serializers.ChoiceField(choices=["result"])
    data = PredictResponseSerializer()  # type: ignore[assignment]


class ErrorFrameSerializer(serializers.Serializer[dict[str, Any]]):
    event = serializers.ChoiceField(choices=["error"])
    data = StreamErrorDataSerializer()  # type: ignore[assignment]


PREDICT_STREAM_FRAME = PolymorphicProxySerializer(
    component_name="PredictStreamFrame",
    serializers={
        "conversation": ConversationFrameSerializer,
        "quota": QuotaFrameSerializer,
        "stage": StageFrameSerializer,
        "result": ResultFrameSerializer,
        "error": ErrorFrameSerializer,
    },
    resource_type_field_name="event",
)
