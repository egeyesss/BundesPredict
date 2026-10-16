from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer, not_implemented

from .serializers import MeSerializer, MeUpdateSerializer


class MeView(APIView):
    @extend_schema(
        operation_id="me_retrieve",
        tags=["accounts"],
        responses={200: MeSerializer, 401: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()

    @extend_schema(
        operation_id="me_partial_update",
        tags=["accounts"],
        request=MeUpdateSerializer,
        responses={200: MeSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
        description="`email_opt_in` and `timezone` are the only writable fields.",
    )
    def patch(self, request: Request) -> Response:
        MeUpdateSerializer(data=request.data, partial=True).is_valid(raise_exception=True)
        return not_implemented()
