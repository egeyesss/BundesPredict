from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer, not_implemented

from .serializers import UnsubscribeSerializer


class UnsubscribeView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="email_unsubscribe",
        tags=["notifications"],
        request=UnsubscribeSerializer,
        responses={204: OpenApiResponse(description="Unsubscribed."), 400: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        UnsubscribeSerializer(data=request.data).is_valid(raise_exception=True)
        return not_implemented()
