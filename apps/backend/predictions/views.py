from __future__ import annotations

from collections.abc import Iterable

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request
from rest_framework.views import APIView

from config.api import ErrorSerializer, ModelUnavailable

from .llm import agent_model, get_llm_client
from .ports import DjangoAgentPorts
from .serializers import (
    PREDICT_STREAM_FRAME,
    PredictRequestSerializer,
    QuotaExceededErrorSerializer,
)
from .stream import stream_prediction
from .throttles import PredictThrottle

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
    permission_classes = [AllowAny]
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
            429: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> StreamingHttpResponse:
        serializer = PredictRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query: str = serializer.validated_data["query"]
        client = get_llm_client()
        serving = DjangoAgentPorts().latest_ratings()
        if serving is None:
            raise ModelUnavailable()

        response = StreamingHttpResponse(
            stream_prediction(query, serving, client, agent_model()),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
