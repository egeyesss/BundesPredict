from __future__ import annotations

from typing import Any

from rest_framework import serializers


class BillingRedirectSerializer(serializers.Serializer[dict[str, Any]]):
    url = serializers.URLField(help_text="Hosted Stripe page to send the browser to.")
