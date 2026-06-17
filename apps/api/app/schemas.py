"""Request/response models for the prediction endpoint.

These build on the agent's existing serializers (``markets_to_dict`` /
``_applied_adjustment``) so the HTTP shape stays consistent with what the tools
hand the LLM — one source of truth for how a distribution looks.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from bundespredict.agent.loop import AgentResult
from bundespredict.agent.service import PredictionRecord
from bundespredict.agent.tools import _applied_adjustment, markets_to_dict


class PredictRequest(BaseModel):
    query: str = Field(min_length=1, description="natural-language match question")
    match_date: date | None = Field(
        default=None,
        description="fixture date; scopes form lookups so nothing after it leaks in",
    )


class ScoreOut(BaseModel):
    home: int
    away: int
    p: float


class MarketsOut(BaseModel):
    p_home: float
    p_draw: float
    p_away: float
    p_over_2_5: float
    p_under_2_5: float
    p_btts: float
    exp_home_goals: float
    exp_away_goals: float
    top_scores: list[ScoreOut]


class AppliedAdjustmentOut(BaseModel):
    factor: str
    team: str | None
    target: str
    requested_magnitude_xg: float
    effective_magnitude_xg: float
    confidence: str
    rationale: str


class PredictResponse(BaseModel):
    """The agent's answer: baseline vs. adjusted, the adjustments, the words."""

    home: str | None
    away: str | None
    explanation: str
    baseline: MarketsOut | None
    adjusted: MarketsOut | None
    adjustments: list[AppliedAdjustmentOut]
    prediction_id: int | None


def _markets_out(markets: object) -> MarketsOut:
    # markets is a Markets; markets_to_dict yields exactly MarketsOut's shape.
    return MarketsOut(**markets_to_dict(markets))  # type: ignore[arg-type]


def build_response(
    result: AgentResult, record: PredictionRecord | None, prediction_id: int | None
) -> PredictResponse:
    """Assemble the HTTP response from an agent run and its persisted id."""
    if record is None:
        # The agent answered without predicting a fixture (e.g. a clarification).
        return PredictResponse(
            home=None,
            away=None,
            explanation=result.explanation,
            baseline=None,
            adjusted=None,
            adjustments=[],
            prediction_id=None,
        )
    return PredictResponse(
        home=record.home,
        away=record.away,
        explanation=result.explanation,
        baseline=_markets_out(record.baseline),
        adjusted=_markets_out(record.adjusted) if record.adjusted is not None else None,
        adjustments=[AppliedAdjustmentOut(**_applied_adjustment(a)) for a in record.adjustments],
        prediction_id=prediction_id,
    )
