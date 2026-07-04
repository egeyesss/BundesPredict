"""End-to-end test of the /predict endpoint (Postgres + scripted client).

Overrides the two dependencies — DB session and LLM client — so the real app,
router, serialization, and persistence run against a throwaway Postgres and a
recorded transcript, with no network and no API key.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.deps import get_llm_client, get_session
from app.main import app
from bundespredict.data.db import make_session_factory
from bundespredict.data.models import Prediction, Team
from bundespredict.data.params_store import save_ratings
from bundespredict.model.dixon_coles import TeamRatings
from tests.agent.fakes import FakeResponse, ScriptedClient, transcript_full

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"


def _seed_run(session: Session) -> None:
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
    save_ratings(session, ratings, xi=0.0, n_matches=0)


def _client(pg_engine: Engine, *, responses: list[FakeResponse] | None = None) -> TestClient:
    factory = make_session_factory(pg_engine)

    def _session_override() -> Iterator[Session]:
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_llm_client] = lambda: ScriptedClient(
        responses if responses is not None else transcript_full(HOME, AWAY)
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def test_predict_returns_baseline_and_adjusted_and_persists(
    session: Session, pg_engine: Engine
) -> None:
    _seed_run(session)
    client = _client(pg_engine)

    resp = client.post("/predict", json={"query": "striker out, windy"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["home"] == HOME and body["away"] == AWAY
    assert body["adjusted"]["p_home"] < body["baseline"]["p_home"]
    assert len(body["adjustments"]) == 2
    assert body["adjustments"][0]["effective_magnitude_xg"] == -0.35
    assert "47%" in body["explanation"]
    assert body["prediction_id"] is not None

    # The answer was persisted as an audit row.
    count = session.execute(select(func.count()).select_from(Prediction)).scalar_one()
    assert count == 1


def test_predict_response_includes_the_score_grid(session: Session, pg_engine: Engine) -> None:
    _seed_run(session)
    client = _client(pg_engine)

    body = client.post("/predict", json={"query": "striker out, windy"}).json()

    grid = body["baseline"]["score_grid"]
    assert len(grid) == 11 and all(len(row) == 11 for row in grid)
    assert sum(sum(row) for row in grid) == pytest.approx(1.0, abs=1e-4)
    # The grid is consistent with the sliced markets it shipped with.
    top = body["baseline"]["top_scores"][0]
    assert grid[top["home"]][top["away"]] == pytest.approx(top["p"], abs=1e-4)


def _parse_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE body into (event, data) pairs."""
    frames = []
    for chunk in text.strip().split("\n\n"):
        lines = chunk.split("\n")
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        frames.append((event, json.loads(data)))
    return frames


def test_predict_stream_stages_then_result(session: Session, pg_engine: Engine) -> None:
    _seed_run(session)
    client = _client(pg_engine)

    resp = client.post("/predict/stream", json={"query": "striker out, windy"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse(resp.text)

    # One stage per tool_call/tool_result of the transcript, then the result.
    kinds = [event for event, _ in frames]
    assert kinds == ["stage"] * 6 + ["result"]
    stage_types = [data["type"] for event, data in frames if event == "stage"]
    assert stage_types == ["tool_call", "tool_result"] * 3

    # The terminal result event is the same shape /predict returns.
    result = frames[-1][1]
    assert result["home"] == HOME and result["away"] == AWAY
    assert result["adjusted"]["p_home"] < result["baseline"]["p_home"]
    assert len(result["adjustments"]) == 2
    assert result["prediction_id"] is not None

    # And it was persisted exactly once, like the non-streaming path.
    count = session.execute(select(func.count()).select_from(Prediction)).scalar_one()
    assert count == 1


def test_predict_stream_503_without_a_fitted_model(session: Session, pg_engine: Engine) -> None:
    # Setup failures happen before any frame is sent, so they are real statuses.
    client = _client(pg_engine)
    resp = client.post("/predict/stream", json={"query": "anything"})
    assert resp.status_code == 503


def test_predict_forwards_history_to_the_loop(session: Session, pg_engine: Engine) -> None:
    _seed_run(session)
    responses = transcript_full(HOME, AWAY)
    scripted = ScriptedClient(responses)
    factory_client = _client(pg_engine)
    app.dependency_overrides[get_llm_client] = lambda: scripted

    history = [
        {"role": "user", "content": "predict Dortmund vs Leipzig"},
        {"role": "assistant", "content": "Baseline: home 55%."},
    ]
    resp = factory_client.post(
        "/predict", json={"query": "and if their striker is out?", "history": history}
    )

    assert resp.status_code == 200
    sent = scripted.messages.calls[0]["messages"]
    assert sent[0]["content"] == "predict Dortmund vs Leipzig"
    assert sent[1]["role"] == "assistant"
    assert sent[2]["content"] == "and if their striker is out?"


def test_predict_rejects_oversized_history(session: Session, pg_engine: Engine) -> None:
    _seed_run(session)
    client = _client(pg_engine)
    turns = [{"role": "user", "content": f"q{i}"} for i in range(41)]
    resp = client.post("/predict", json={"query": "x", "history": turns})
    assert resp.status_code == 422


def test_predict_requires_a_query(session: Session, pg_engine: Engine) -> None:
    _seed_run(session)
    client = _client(pg_engine)
    resp = client.post("/predict", json={"query": ""})
    assert resp.status_code == 422  # empty query fails schema validation


def test_predict_503_without_a_fitted_model(session: Session, pg_engine: Engine) -> None:
    # No model run seeded -> nothing to serve.
    client = _client(pg_engine)
    resp = client.post("/predict", json={"query": "anything"})
    assert resp.status_code == 503
    assert "no fitted model" in resp.json()["detail"]
