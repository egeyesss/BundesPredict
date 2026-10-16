from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import not_implemented

from .serializers import TrackRecordQuerySerializer, TrackRecordSerializer


class TrackRecordView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="track_record_retrieve",
        tags=["track-record"],
        parameters=[TrackRecordQuerySerializer],
        responses=TrackRecordSerializer,
        description="Live results of frozen predictions, kept apart from the backtest.",
    )
    def get(self, request: Request) -> Response:
        return not_implemented()
