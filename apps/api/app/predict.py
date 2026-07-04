"""The prediction endpoints: HTTP in, agent + engine behind them.

This is the seam the plan describes — the chat UI (and anyone else) reaches the
agent through here. The endpoints are deliberately thin: they load the latest
*persisted* model run (serving never refits), run the agent loop, persist the
answer, and return the baseline-vs-adjusted distributions plus the adjustments
and explanation. All the math, validation, and clamping live below them.

``POST /predict`` answers in one shot; ``POST /predict/stream`` sends the same
answer over SSE, preceded by a ``stage`` event per agent step so the UI can show
the run as it happens (which tool, with what input) instead of a spinner.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from bundespredict.agent.loop import AgentResult, LLMClient, run_agent, run_agent_events
from bundespredict.agent.service import PredictionService
from bundespredict.data.params_store import latest_run_id, load_ratings
from bundespredict.data.predictions_store import save_prediction

from .config import Settings, get_settings
from .deps import get_llm_client, get_session
from .schemas import PredictRequest, PredictResponse, build_response

logger = logging.getLogger(__name__)

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
ClientDep = Annotated[LLMClient, Depends(get_llm_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _load_service(session: Session, req: PredictRequest) -> tuple[int, PredictionService]:
    """Latest persisted run + a service over it, or 503 when nothing is fitted."""
    run_id = latest_run_id(session)
    if run_id is None:
        raise HTTPException(status_code=503, detail="no fitted model available yet")
    ratings = load_ratings(session, run_id)
    return run_id, PredictionService(ratings, session=session, as_of_date=req.match_date)


def _history(req: PredictRequest) -> list[dict[str, Any]]:
    """The request's prior turns in the message shape the loop expects."""
    return [{"role": turn.role, "content": turn.content} for turn in req.history]


def _persist_and_build(
    session: Session, run_id: int, req: PredictRequest, result: AgentResult
) -> PredictResponse:
    """Save the audit row (when a fixture was predicted) and shape the response."""
    record = result.record
    prediction_id = None
    if record is not None:
        prediction_id = save_prediction(
            session,
            model_run_id=run_id,
            record=record,
            explanation=result.explanation,
            query=req.query,
            match_date=req.match_date,
        )
    return build_response(result, record, prediction_id)


@router.post("/predict", response_model=PredictResponse)
def predict(
    req: PredictRequest,
    session: SessionDep,
    client: ClientDep,
    settings: SettingsDep,
) -> PredictResponse:
    """Answer a natural-language match question with a calibrated, audited prediction."""
    run_id, service = _load_service(session, req)
    result = run_agent(
        req.query, service, client=client, history=_history(req), model=settings.agent_model
    )
    return _persist_and_build(session, run_id, req, result)


def _sse(event: str, data: dict[str, Any]) -> str:
    """One server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/predict/stream")
def predict_stream(
    req: PredictRequest,
    session: SessionDep,
    client: ClientDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """Same answer as ``/predict``, streamed as SSE with per-step ``stage`` events.

    Frames: zero or more ``stage`` events (one per tool call / result), then a
    single ``result`` event carrying the full response body. Errors after the
    stream has started can't change the HTTP status anymore, so they arrive as
    an ``error`` event instead; the setup failures that *can* still be real
    status codes (no fitted model, no API key) are raised before streaming.
    """
    run_id, service = _load_service(session, req)

    def frames() -> Iterator[str]:
        try:
            result: AgentResult | None = None
            for event in run_agent_events(
                req.query,
                service,
                client=client,
                history=_history(req),
                model=settings.agent_model,
            ):
                if event.type == "final":
                    result = event.result
                else:
                    yield _sse("stage", {"type": event.type, **event.data})
            assert result is not None  # the loop always ends with a final event
            response = _persist_and_build(session, run_id, req, result)
            yield _sse("result", response.model_dump(mode="json"))
        except Exception:
            logger.exception("streaming prediction failed")
            yield _sse("error", {"detail": "prediction failed; check the API logs"})

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Tells buffering reverse proxies (nginx & friends) to pass frames
            # through as they're produced — otherwise "streaming" arrives in one lump.
            "X-Accel-Buffering": "no",
        },
    )
