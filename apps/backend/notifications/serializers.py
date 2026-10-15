from __future__ import annotations

from typing import Any

from rest_framework import serializers


class UnsubscribeSerializer(serializers.Serializer[dict[str, Any]]):
    token = serializers.CharField(help_text="Signed token from the email's unsubscribe link.")
