from __future__ import annotations

from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import MeSerializer
from config.api import ErrorSerializer, not_implemented

from .metrics import build_metrics
from .serializers import AdminMetricsSerializer

RANGES = (7, 30, 90)


def _is_staff(user: User) -> bool:
    return user.is_staff or user.is_superuser


def _is_demo(user: User) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_demo)


class AdminMetricsView(APIView):
    @extend_schema(
        operation_id="admin_metrics_retrieve",
        tags=["ops"],
        parameters=[
            OpenApiParameter(
                "days", int, enum=list(RANGES), description="Length of `chats_per_day`; default 30."
            )
        ],
        responses={
            200: AdminMetricsSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
        },
        description="Admins see real values; demo users get the same numbers with emails masked.",
    )
    def get(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        masked = not _is_staff(user)
        if masked and not _is_demo(user):
            raise PermissionDenied
        raw_days = request.query_params.get("days", "30")
        if raw_days not in {str(option) for option in RANGES}:
            raise ValidationError({"days": [f"Use one of {', '.join(map(str, RANGES))}."]})
        return Response(
            AdminMetricsSerializer(build_metrics(days=int(raw_days), masked=masked)).data
        )


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
