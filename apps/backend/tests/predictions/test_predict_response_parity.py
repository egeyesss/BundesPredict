"""The DRF `PredictResponse` must serialise a run exactly like the FastAPI one does today."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pytest
from rest_framework.renderers import JSONRenderer
from tests.agent.fakes import (
    FakeResponse,
    FakeTextBlock,
    ScriptedClient,
    transcript_full,
    transcript_refusal,
)

from app.schemas import build_response
from bundespredict.agent.loop import AgentResult, run_agent
from bundespredict.agent.service import PredictionService
from bundespredict.model.dixon_coles import TeamRatings
from predictions.serializers import serialize_predict_response

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"
PREDICTION_ID = 42


def _ratings() -> TeamRatings:
    return TeamRatings(
        teams=(HOME, AWAY),
        attack=np.array([0.4, -0.4]),
        defense=np.array([-0.2, 0.2]),
        home_adv=0.3,
        rho=-0.12,
        log_likelihood=0.0,
    )


def _clarification() -> list[FakeResponse]:
    return [
        FakeResponse(
            content=[FakeTextBlock("Which fixture do you mean?")],
            stop_reason="end_turn",
        )
    ]


TRANSCRIPTS = {
    "full": transcript_full(HOME, AWAY),
    "refusal": transcript_refusal(HOME, AWAY),
    "clarification": _clarification(),
}


def _run(transcript: list[FakeResponse]) -> AgentResult:
    service = PredictionService(_ratings())
    return run_agent("striker out, windy", service, client=ScriptedClient(transcript), model="x")


def _wire(payload: Any) -> Any:
    """What a client would receive: rendered to JSON text and parsed back."""
    return json.loads(JSONRenderer().render(payload))


@pytest.mark.parametrize("name", TRANSCRIPTS)
def test_drf_serializer_matches_fastapi_response(name: str) -> None:
    result = _run(list(TRANSCRIPTS[name]))
    prediction_id = None if result.record is None else PREDICTION_ID

    fastapi_json = json.loads(
        build_response(result, result.record, prediction_id).model_dump_json()
    )
    drf_json = _wire(serialize_predict_response(result, prediction_id))

    assert drf_json == fastapi_json


def test_full_transcript_covers_adjusted_markets_and_adjustments() -> None:
    """Guards the parity test against passing on two equally empty payloads."""
    result = _run(list(TRANSCRIPTS["full"]))

    payload = _wire(serialize_predict_response(result, PREDICTION_ID))

    assert payload["adjusted"] is not None
    assert len(payload["adjustments"]) == 2
    assert len(payload["baseline"]["score_grid"]) == 11
    assert payload["prediction_id"] == PREDICTION_ID


def test_clarification_has_null_markets() -> None:
    result = _run(list(TRANSCRIPTS["clarification"]))

    payload = _wire(serialize_predict_response(result, None))

    assert payload == {
        "home": None,
        "away": None,
        "explanation": "Which fixture do you mean?",
        "baseline": None,
        "adjusted": None,
        "adjustments": [],
        "prediction_id": None,
    }
