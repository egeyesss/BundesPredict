from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import MeSerializer
from config.api import ErrorSerializer, not_implemented

from .serializers import AdminMetricsSerializer


class AdminMetricsView(APIView):
    @extend_schema(
        operation_id="admin_metrics_retrieve",
        tags=["ops"],
        responses={
            200: AdminMetricsSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
        },
        description="Admins see real values; demo users get the same numbers with emails masked.",
    )
    def get(self, request: Request) -> Response:
        return not_implemented()


class DemoStartView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="demo_start",
        tags=["ops"],
        request=None,
        responses={201: MeSerializer, 429: ErrorSerializer},
        description="Creates a throwaway demo user and signs the browser in as them.",
    )
    def post(self, request: Request) -> Response:
        return not_implemented()
