from __future__ import annotations

from typing import Any

from rest_framework import serializers

from predictions.serializers import PredictResponseSerializer


class ConversationSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    title = serializers.CharField()
    fixture_id = serializers.IntegerField(allow_null=True)
    updated_at = serializers.DateTimeField()


class MessageSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()
    prediction = PredictResponseSerializer(
        allow_null=True, help_text="Set on assistant messages that answered with a prediction."
    )
    created_at = serializers.DateTimeField()


class ConversationSerializer(ConversationSummarySerializer):
    messages = MessageSerializer(many=True)


class ConversationPageSerializer(serializers.Serializer[dict[str, Any]]):
    """One page of the newest-first list; follow `next` for older conversations."""

    next = serializers.CharField(allow_null=True, help_text="Opaque cursor, null on the last page.")
    results = ConversationSummarySerializer(many=True)
