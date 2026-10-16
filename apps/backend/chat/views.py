from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer

from .models import Conversation
from .serializers import (
    ConversationPageSerializer,
    ConversationSerializer,
    ConversationSummarySerializer,
)
from .services import owned_conversation

MAX_PAGE_SIZE = 50


class ConversationCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "limit"
    max_page_size = MAX_PAGE_SIZE
    ordering = "-updated_at"

    def get_paginated_response(self, data: Any) -> Response:
        link = self.get_next_link()
        cursor = parse_qs(urlparse(link).query)[self.cursor_query_param][0] if link else None
        return Response({"next": cursor, "results": data})


def _summary(conversation: Conversation) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "fixture_id": conversation.fixture_id,
        "updated_at": conversation.updated_at,
    }


def _detail_payload(conversation: Conversation) -> dict[str, Any]:
    messages = conversation.messages.select_related("prediction")
    return {
        **_summary(conversation),
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "prediction": message.prediction.response_json if message.prediction else None,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


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
        user: User = request.user  # type: ignore[assignment]
        paginator = ConversationCursorPagination()
        page = paginator.paginate_queryset(Conversation.objects.filter(user=user), request, self)
        rows = [_summary(conversation) for conversation in page or []]
        data = ConversationSummarySerializer(rows, many=True).data
        return paginator.get_paginated_response(data)


class ConversationDetailView(APIView):
    @extend_schema(
        operation_id="conversations_retrieve",
        tags=["chat"],
        responses={200: ConversationSerializer, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def get(self, request: Request, id: uuid.UUID) -> Response:
        user: User = request.user  # type: ignore[assignment]
        conversation = owned_conversation(user, id)
        return Response(ConversationSerializer(_detail_payload(conversation)).data)

    @extend_schema(
        operation_id="conversations_destroy",
        tags=["chat"],
        responses={204: None, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def delete(self, request: Request, id: uuid.UUID) -> Response:
        user: User = request.user  # type: ignore[assignment]
        owned_conversation(user, id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
