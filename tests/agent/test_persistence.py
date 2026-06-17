"""Postgres-backed test: an agent run is persisted as an auditable row."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.agent.loop import run_agent
from bundespredict.agent.service import PredictionService
from bundespredict.data.models import Prediction, Team
from bundespredict.data.params_store import load_ratings, save_ratings
from bundespredict.data.predictions_store import save_prediction
from bundespredict.model.dixon_coles import TeamRatings

from .fakes import ScriptedClient, transcript_full

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"


def _seed_run(session: Session) -> int:
    """Two teams + a persisted model run; returns the run id (serving reads it)."""
    session.add_all([Team(name=HOME), Team(name=AWAY)])
    session.commit()
    ratings = TeamRatings(
        teams=(HOME, AWAY),
        attack=np.array([0.4, -0.4]),
        defense=np.array([-0.2, 0.2]),
        home_adv=0.3,
        rho=-0.12,
        log_likelihood=0.0,
    )
    return save_ratings(session, ratings, xi=0.0, n_matches=0)


def test_agent_run_is_persisted_and_auditable(session: Session) -> None:
    run_id = _seed_run(session)
    # Serving reads persisted params, never refits.
    ratings = load_ratings(session, run_id)
    service = PredictionService(ratings, session=session)

    client = ScriptedClient(transcript_full(HOME, AWAY))
    result = run_agent("striker out, windy", service, client=client)
    assert result.record is not None

    pred_id = save_prediction(
        session,
        model_run_id=run_id,
        record=result.record,
        explanation=result.explanation,
        query="striker out, windy",
    )

    row = session.get(Prediction, pred_id)
    assert row is not None
    # Served distribution is the adjusted one; baseline is kept alongside it.
    assert row.p_home < row.base_p_home
    assert abs(row.p_home + row.p_draw + row.p_away - 1.0) < 1e-3
    assert row.query == "striker out, windy"
    assert row.explanation == result.explanation

    # The adjustments are logged with both requested and effective magnitudes.
    assert len(row.adjustments_json) == 2
    first = row.adjustments_json[0]
    assert first["factor"] == "player_out"
    assert first["requested_magnitude_xg"] == -0.35
    assert first["effective_magnitude_xg"] == -0.35  # in range, so unchanged

    # Foreign keys resolved to the right teams.
    home = session.execute(select(Team.name).where(Team.id == row.home_id)).scalar_one()
    assert home == HOME


def test_clamped_magnitude_is_recorded_as_effective(session: Session) -> None:
    run_id = _seed_run(session)
    ratings = load_ratings(session, run_id)
    service = PredictionService(ratings, session=session)

    # Hand an out-of-range request straight to the service (as if the LLM asked).
    from bundespredict.agent.adjustments import Adjustment

    service.predict_with_context(
        HOME,
        AWAY,
        [
            Adjustment(
                factor="player_out",
                team="home",
                target="home_attack",
                magnitude_xg=-5.0,
                confidence="high",
                rationale="absurd",
            )
        ],
    )
    assert service.last_prediction is not None
    pred_id = save_prediction(session, model_run_id=run_id, record=service.last_prediction)

    row = session.get(Prediction, pred_id)
    assert row is not None
    logged = row.adjustments_json[0]
    assert logged["requested_magnitude_xg"] == -5.0
    assert logged["effective_magnitude_xg"] == -0.6  # clamped
