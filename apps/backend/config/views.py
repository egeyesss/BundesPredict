from django.db import Error, connection
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from football.repositories import SERVING_VERSION, latest_model_run


class HealthSerializer(serializers.Serializer[dict[str, object]]):
    status = serializers.ChoiceField(choices=["ok", "error"])
    model_run_id = serializers.IntegerField(allow_null=True)
    db = serializers.ChoiceField(choices=["ok", "unavailable"])


class HealthView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(responses={200: HealthSerializer, 503: HealthSerializer})
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Error:
            body = {"status": "error", "model_run_id": None, "db": "unavailable"}
            return Response(body, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        run = latest_model_run(version=SERVING_VERSION)
        return Response({"status": "ok", "model_run_id": run.pk if run else None, "db": "ok"})
