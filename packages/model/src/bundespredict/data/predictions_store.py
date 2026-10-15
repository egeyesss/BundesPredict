"""Persist agent predictions so every answer is auditable.

The agent run yields a :class:`~bundespredict.agent.service.PredictionRecord`
(baseline + adjusted + the applied adjustments) and an explanation; this writes
that as one ``predictions`` row tied to the model run that produced it. Like the
rest of the data layer it lives here because it is the side that touches the
database — the agent and engine never do.

The ``adjustments_json`` payload records each adjustment's *requested* magnitude
and the *effective* (clamped) one, so a reviewer can see both what the LLM asked
for and what the engine actually applied.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.agent.service import PredictionRecord
from bundespredict.model.adjust import clamp_magnitude

from .models import Prediction, Team


def _adjustments_payload(record: PredictionRecord) -> list[dict[str, object]]:
    return [
        {
            "factor": a.factor,
            "team": a.team,
            "target": a.target,
            "requested_magnitude_xg": a.magnitude_xg,
            "effective_magnitude_xg": clamp_magnitude(a.magnitude_xg),
            "confidence": a.confidence,
            "rationale": a.rationale,
        }
        for a in record.adjustments
    ]


def save_prediction(
    session: Session,
    *,
    model_run_id: int,
    record: PredictionRecord,
    explanation: str | None = None,
    query: str | None = None,
    match_date: date | None = None,
) -> int:
    """Write one prediction row and return its id.

    Resolves the fixture's canonical team names to ids; raises ``ValueError`` if
    either is unknown. Commits so the audit record is durable.
    """
    name_to_id: dict[str, int] = dict(
        session.execute(select(Team.name, Team.id).where(Team.name.in_([record.home, record.away])))
        .tuples()
        .all()
    )
    missing = {record.home, record.away} - name_to_id.keys()
    if missing:
        raise ValueError(f"no teams row for: {sorted(missing)}")

    served = record.served
    baseline = record.baseline
    prediction = Prediction(
        model_run_id=model_run_id,
        home_id=name_to_id[record.home],
        away_id=name_to_id[record.away],
        match_date=match_date,
        query=query,
        p_home=served.p_home,
        p_draw=served.p_draw,
        p_away=served.p_away,
        exp_home_goals=served.exp_home_goals,
        exp_away_goals=served.exp_away_goals,
        base_p_home=baseline.p_home,
        base_p_draw=baseline.p_draw,
        base_p_away=baseline.p_away,
        adjustments_json=_adjustments_payload(record),
        explanation=explanation,
    )
    session.add(prediction)
    session.commit()
    return prediction.id
