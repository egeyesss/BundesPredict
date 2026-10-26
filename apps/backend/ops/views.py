from __future__ import annotations

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.me import serialize_me
from accounts.serializers import MeSerializer
from config.api import ErrorSerializer
from predictions.throttles import CLIENT_IP_META

from .demo import DEMO_LIFETIME, DemoLimitReached, start_demo
from .metrics import build_metrics
from .serializers import AdminMetricsSerializer

RANGES = (7, 30, 90)
DEMO_LOGIN_BACKEND = "django.contrib.auth.backends.ModelBackend"
UNKNOWN_CLIENT = "unknown"


def _is_staff(user: User) -> bool:
    return user.is_staff or user.is_superuser


def _is_demo(user: User) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_demo)


def _client_ip(request: Request) -> str | None:
    """The address the web proxy forwarded; its `unknown` marker means there is none."""
    forwarded = request.META.get(CLIENT_IP_META, "").strip()
    return None if forwarded in ("", UNKNOWN_CLIENT) else forwarded


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
        description=(
            "Creates a throwaway demo user with two saved chats and signs the browser in as "
            "them. 429 carries `demo_ip_limit` or `demo_budget`."
        ),
    )
    def post(self, request: Request) -> Response:
        try:
            with transaction.atomic():
                user = start_demo(client_ip=_client_ip(request))
                login(request, user, backend=DEMO_LOGIN_BACKEND)
                request.session.set_expiry(int(DEMO_LIFETIME.total_seconds()))
        except DemoLimitReached as limit:
            return Response(
                {"code": limit.code, "message": limit.message},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return Response(serialize_me(user, user.profile), status=status.HTTP_201_CREATED)
