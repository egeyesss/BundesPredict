from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer, not_implemented

from .serializers import (
    PREDICT_STREAM_FRAME,
    PredictRequestSerializer,
    QuotaExceededErrorSerializer,
)

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


class PredictStreamView(APIView):
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
    def post(self, request: Request) -> Response:
        PredictRequestSerializer(data=request.data).is_valid(raise_exception=True)
        return not_implemented()
