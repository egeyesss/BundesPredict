"""The prediction endpoint: HTTP in, agent + engine behind it.

This is the seam the plan describes — the chat UI (and anyone else) reaches the
agent through here. The endpoint is deliberately thin: it loads the latest
*persisted* model run (serving never refits), runs the agent loop, persists the
answer, and returns the baseline-vs-adjusted distributions plus the adjustments
and explanation. All the math, validation, and clamping live below it.

Non-streaming for v1; token/tool streaming over SSE is a later refinement.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bundespredict.agent.loop import LLMClient, run_agent
from bundespredict.agent.service import PredictionService
from bundespredict.data.params_store import latest_run_id, load_ratings
from bundespredict.data.predictions_store import save_prediction

from .config import Settings, get_settings
from .deps import get_llm_client, get_session
from .schemas import PredictRequest, PredictResponse, build_response

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
ClientDep = Annotated[LLMClient, Depends(get_llm_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("/predict", response_model=PredictResponse)
def predict(
    req: PredictRequest,
    session: SessionDep,
    client: ClientDep,
    settings: SettingsDep,
) -> PredictResponse:
    """Answer a natural-language match question with a calibrated, audited prediction."""
    run_id = latest_run_id(session)
    if run_id is None:
        raise HTTPException(status_code=503, detail="no fitted model available yet")

    ratings = load_ratings(session, run_id)
    service = PredictionService(ratings, session=session, as_of_date=req.match_date)

    result = run_agent(req.query, service, client=client, model=settings.agent_model)

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
