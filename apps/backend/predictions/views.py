from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import User
from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import plans, quota
from accounts.serializers import UsageSerializer
from chat.models import Conversation
from chat.services import owned_conversation
from config.api import ErrorSerializer, ModelUnavailable
from football.models import Fixture

from .llm import agent_model, get_llm_client
from .ports import DjangoAgentPorts
from .serializers import (
    PREDICT_STREAM_FRAME,
    PredictRequestSerializer,
    QuotaExceededErrorSerializer,
)
from .stream import stream_prediction
from .throttles import PredictThrottle

UPGRADE_URL = "/account"

STREAM_DESCRIPTION = """\
Runs the agent and streams its progress as server-sent events.

Each frame is `event: <name>` and `data: <json>` followed by a blank line, flushed as soon as it is
produced. The response schema describes one decoded frame: `event` is the frame name and `data` is
its JSON payload.

| event | data | when |
|---|---|---|
| `conversation` | `ConversationEventData` | first frame, always |
| `quota` | `Usage` | right after the chat is counted |
| `stage` | `ToolCallStage` or `ToolResultStage` | each agent step |
| `result` | `PredictResponse` | once, at the end |
| `error` | `StreamErrorData` | instead of `result` when the run fails after the stream started |

Needs a session. Each call spends one chat from the daily quota; a call over the limit is a 402
before any frame. A run that fails before its first model response gives the chat back. Send
`conversation_id` to continue a saved conversation; the server builds the history from it.

Failures before the first frame are plain JSON errors with the statuses listed below.
"""


class AcceptAnythingNegotiation(DefaultContentNegotiation):
    """Serves the stream whatever `Accept` says; an `EventSource` asks for `text/event-stream`.

    The view builds its own response, so the negotiated renderer only matters for error bodies,
    which are always JSON.
    """

    def select_renderer(
        self, request: Request, renderers: Iterable[BaseRenderer], format_suffix: str | None = None
    ) -> tuple[BaseRenderer, str]:
        renderer = next(iter(renderers))
        return renderer, str(renderer.media_type)


class PredictStreamView(APIView):
    throttle_classes = [PredictThrottle]
    content_negotiation_class = AcceptAnythingNegotiation

    @extend_schema(
        operation_id="predict_stream",
        tags=["predictions"],
        request=PredictRequestSerializer,
        description=STREAM_DESCRIPTION,
        responses={
            (200, "text/event-stream"): OpenApiResponse(
                response=PREDICT_STREAM_FRAME, description="A stream of frames."
            ),
            400: ErrorSerializer,
            401: ErrorSerializer,
            402: QuotaExceededErrorSerializer,
            404: ErrorSerializer,
            429: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> StreamingHttpResponse | Response:
        serializer = PredictRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query: str = serializer.validated_data["query"]
        conversation_id = serializer.validated_data["conversation_id"]
        fixture_id = serializer.validated_data["fixture_id"]
        user: User = request.user  # type: ignore[assignment]
        client = get_llm_client()
        serving = DjangoAgentPorts().latest_ratings()
        if serving is None:
            raise ModelUnavailable()
        conversation = owned_conversation(user, conversation_id) if conversation_id else None

        usage = quota.consume(user)
        if usage is None:
            return _quota_exceeded(user)
        if conversation is None:
            try:
                conversation = _start_conversation(user, query, fixture_id)
            except Exception:
                quota.refund(user)
                raise

        model = agent_model()
        response = StreamingHttpResponse(
            stream_prediction(
                query, serving, client, model, user=user, conversation=conversation, usage=usage
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


def _start_conversation(user: User, query: str, fixture_id: int | None) -> Conversation:
    fixture = Fixture.objects.filter(pk=fixture_id).first() if fixture_id is not None else None
    return Conversation.objects.create(
        user=user, title=Conversation.title_for(query), fixture=fixture
    )


def _quota_exceeded(user: User) -> Response:
    usage = quota.current(user)
    return Response(
        {
            "code": "quota_exceeded",
            "message": (
                "You have used all of your demo chats."
                if plans.is_demo(user)
                else "You have used all of today's chats."
            ),
            "usage": UsageSerializer(
                {"used": usage.used, "limit": usage.limit, "resets_at": usage.resets_at}
            ).data,
            "upgrade_url": UPGRADE_URL,
        },
        status=status.HTTP_402_PAYMENT_REQUIRED,
    )
