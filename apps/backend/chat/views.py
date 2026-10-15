from __future__ import annotations

import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer, not_implemented

from .serializers import ConversationPageSerializer, ConversationSerializer


class ConversationListView(APIView):
    @extend_schema(
        operation_id="conversations_list",
        tags=["chat"],
        parameters=[
            OpenApiParameter("cursor", OpenApiTypes.STR, description="`next` from the last page."),
            OpenApiParameter("limit", OpenApiTypes.INT, description="Page size, 1 to 50."),
        ],
        responses={200: ConversationPageSerializer, 401: ErrorSerializer},
        description="The signed-in user's conversations, newest first, cursor-paginated.",
    )
    def get(self, request: Request) -> Response:
        return not_implemented()


class ConversationDetailView(APIView):
    @extend_schema(
        operation_id="conversations_retrieve",
        tags=["chat"],
        responses={200: ConversationSerializer, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def get(self, request: Request, id: uuid.UUID) -> Response:
        return not_implemented()

    @extend_schema(
        operation_id="conversations_destroy",
        tags=["chat"],
        responses={204: None, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def delete(self, request: Request, id: uuid.UUID) -> Response:
        return not_implemented()
