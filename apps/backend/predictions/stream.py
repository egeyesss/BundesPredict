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
from dataclasses import asdict
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.db import transaction

from accounts import quota
from accounts.serializers import UsageSerializer
from bundespredict.agent.loop import AgentEvent, AgentResult, LLMClient, run_agent_events
from bundespredict.agent.ports import PredictionStore, ServingRun
from bundespredict.agent.service import PredictionService
from chat.models import Conversation, Message
from chat.services import history_for

from . import pricing
from .models import Prediction
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


def _persist_turn(
    ports: DjangoAgentPorts,
    serving: ServingRun,
    user: User,
    conversation: Conversation,
    query: str,
    result: AgentResult,
    model: str,
) -> dict[str, Any]:
    """Saves the audit row and both messages together; returns the `result` frame payload."""
    with transaction.atomic():
        prediction_id = _save(ports, serving.run_id, query, result)
        payload = serialize_predict_response(result, prediction_id)
        if prediction_id is not None:
            Prediction.objects.filter(pk=prediction_id).update(
                user=user,
                conversation=conversation,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cost_usd=pricing.cost_usd(
                    model, result.usage.input_tokens, result.usage.output_tokens
                ),
                response_json=payload,
            )
        Message.objects.create(conversation=conversation, role="user", content=query)
        Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=result.explanation,
            prediction_id=prediction_id,
        )
        conversation.save(update_fields=["updated_at"])
    return payload


def _settle_failure(user: User, conversation: Conversation, query: str, tokens_spent: bool) -> None:
    """Keeps the question and, if no LLM call finished, gives the chat back.

    A run that failed after a call completed has already spent tokens, so its chat stays counted.
    """
    if not tokens_spent:
        quota.refund(user)
    Message.objects.create(conversation=conversation, role="user", content=query)
    conversation.save(update_fields=["updated_at"])


async def stream_prediction(
    query: str,
    serving: ServingRun,
    client: LLMClient,
    model: str,
    *,
    user: User,
    conversation: Conversation,
    usage: quota.Usage,
) -> AsyncIterator[str]:
    """Frames for one chat turn: `conversation`, `quota`, a `stage` per tool step, then `result`.

    The turn has already been counted against the quota. A failure here cannot change the HTTP
    status any more, so it is logged and sent as an `error` frame whose message never carries the
    exception text.
    """
    yield sse_frame("conversation", {"id": str(conversation.id), "title": conversation.title})
    yield sse_frame("quota", dict(UsageSerializer(asdict(usage)).data))

    ports = DjangoAgentPorts()
    llm_call_finished = False
    try:
        history = await sync_to_async(history_for)(conversation)
        events = run_agent_events(
            query,
            PredictionService(serving.ratings, ports=ports),
            client=client,
            history=history,
            model=model,
        )
        result: AgentResult | None = None
        while (event := await sync_to_async(_next_event)(events)) is not None:
            # The loop yields only after a model response, so any event means tokens were spent.
            llm_call_finished = True
            if event.type == "final":
                result = event.result
            else:
                yield sse_frame("stage", stage_data(event))
        assert result is not None  # the loop always ends with a final event
        payload = await sync_to_async(_persist_turn)(
            ports, serving, user, conversation, query, result, model
        )
        yield sse_frame("result", payload)
    except Exception:
        logger.exception("streaming prediction failed")
        try:
            await sync_to_async(_settle_failure)(user, conversation, query, llm_call_finished)
        except Exception:
            logger.exception("settling a failed prediction failed")
        yield sse_frame("error", {"code": FAILURE_CODE, "message": FAILURE_MESSAGE})
