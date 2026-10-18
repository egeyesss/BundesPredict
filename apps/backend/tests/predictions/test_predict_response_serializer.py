"""The `PredictResponse` serializer on full, refusal and clarification runs."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from rest_framework.renderers import JSONRenderer
from tests.agent.fakes import (
    FakeResponse,
    FakeTextBlock,
    ScriptedClient,
    transcript_full,
    transcript_refusal,
)

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


def test_full_transcript_serializes_adjusted_markets_and_adjustments() -> None:
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


def test_refusal_keeps_the_baseline_and_reports_no_adjustment() -> None:
    result = _run(list(TRANSCRIPTS["refusal"]))

    payload = _wire(serialize_predict_response(result, PREDICTION_ID))

    assert payload["baseline"] is not None
    assert payload["adjusted"] is None
    assert payload["adjustments"] == []
