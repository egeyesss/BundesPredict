"""The agent run as a server-sent-event stream.

The agent loop is a synchronous generator that blocks on the LLM and the database between
events. Each step runs through `sync_to_async` and the frame is yielded before the next step
starts, so uvicorn flushes it while the agent is still working. The default thread-sensitive
mode is deliberate: Django gives every ASGI request its own worker thread, so all steps of one
stream share a single database connection and `request_finished` closes it, where
`thread_sensitive=False` would open a connection per step and never close any of them.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from asgiref.sync import sync_to_async

from bundespredict.agent.loop import AgentEvent, AgentResult, LLMClient, run_agent_events
from bundespredict.agent.ports import PredictionStore, ServingRun
from bundespredict.agent.service import PredictionService

from .ports import DjangoAgentPorts
from .serializers import serialize_predict_response

logger = logging.getLogger(__name__)

SUMMARY_MAX_LENGTH = 200
FAILURE_CODE = "prediction_failed"
FAILURE_MESSAGE = "The prediction failed. Try again in a moment."


def sse_frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _percent(probability: float) -> str:
    return f"{round(probability * 100)}%"


def _odds(markets: dict[str, Any]) -> str:
    return (
        f"home {_percent(markets['p_home'])}, draw {_percent(markets['p_draw'])}, "
        f"away {_percent(markets['p_away'])}"
    )


def summarize_tool_result(name: str, payload: dict[str, Any], ok: bool) -> str:
    """One short sentence describing a tool outcome, without the raw payload."""
    if not ok:
        reason = payload.get("detail") or payload.get("error") or "the tool failed"
        subject = payload.get("team")
        text = f"{reason}: {subject}" if subject and subject not in str(reason) else str(reason)
        return f"Failed: {text}"[:SUMMARY_MAX_LENGTH]

    if name == "predict_match":
        return f"Baseline: {_odds(payload)}"
    if name == "predict_match_with_context":
        count = len(payload["applied_adjustments"])
        noun = "adjustment" if count == 1 else "adjustments"
        return f"Adjusted ({count} {noun}): {_odds(payload['adjusted'])}"
    if name == "get_team_form":
        return f"{payload['team']}: {payload['record']} over {payload['played']} games"
    if name == "lookup_player":
        if not payload["found"]:
            return f"No record of {payload['name']}"
        return (
            f"{payload['name']} ({payload['team']}, {payload['role']}), "
            f"{payload['importance']} importance"
        )
    if name == "get_recent_results":
        return f"{len(payload['results'])} recent results"
    if name == "get_upcoming_fixtures":
        return f"{len(payload['fixtures'])} upcoming fixtures"
    if name == "get_weather":
        if not payload["available"]:
            return "No forecast available"
        return (
            f"{payload['temperature_c']} C, wind {payload['wind_kmh']} km/h, "
            f"rain {payload['precip_mm']} mm in {payload['city']}"
        )
    return "Done"


def stage_data(event: AgentEvent) -> dict[str, Any]:
    """The `stage` frame payload for a tool call or tool result event."""
    if event.type == "tool_call":
        return {"type": "tool_call", "name": event.data["name"], "input": event.data["input"]}
    ok = event.data["ok"]
    return {
        "type": "tool_result",
        "name": event.data["name"],
        "ok": ok,
        "summary": summarize_tool_result(event.data["name"], event.data["payload"], ok),
    }


def _next_event(events: Iterator[AgentEvent]) -> AgentEvent | None:
    return next(events, None)


def _save(store: PredictionStore, run_id: int, query: str, result: AgentResult) -> int | None:
    if result.record is None:
        return None
    return store.save(
        model_run_id=run_id,
        record=result.record,
        explanation=result.explanation,
        query=query,
        match_date=None,
    )


async def stream_prediction(
    query: str, serving: ServingRun, client: LLMClient, model: str
) -> AsyncIterator[str]:
    """Frames for one run: `conversation`, a `stage` per tool step, then `result` or `error`.

    A failure here cannot change the HTTP status any more, so it is logged and sent as an
    `error` frame whose message never carries the exception text.
    """
    yield sse_frame("conversation", {"id": None, "title": ""})

    ports = DjangoAgentPorts()
    events = run_agent_events(
        query, PredictionService(serving.ratings, ports=ports), client=client, model=model
    )
    try:
        result: AgentResult | None = None
        while (event := await sync_to_async(_next_event)(events)) is not None:
            if event.type == "final":
                result = event.result
            else:
                yield sse_frame("stage", stage_data(event))
        assert result is not None  # the loop always ends with a final event
        prediction_id = await sync_to_async(_save)(ports, serving.run_id, query, result)
        yield sse_frame("result", serialize_predict_response(result, prediction_id))
    except Exception:
        logger.exception("streaming prediction failed")
        yield sse_frame("error", {"code": FAILURE_CODE, "message": FAILURE_MESSAGE})
