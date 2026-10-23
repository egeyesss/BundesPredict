from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .record import build_track_record
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
        query = TrackRecordQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(build_track_record(query.validated_data.get("season")))
