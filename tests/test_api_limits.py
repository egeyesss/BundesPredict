"""Abuse protection on the prediction endpoints.

These cover the three ways an open `/predict` burns Anthropic credit: an
oversized prompt, calling the API directly instead of through the web proxy,
and hammering it in a loop.

No Postgres and no API key here -- the session and LLM dependencies are
overridden, and `latest_run_id` is stubbed to report nothing fitted, so an
allowed request stops at 503 just before the agent would run.

`run_agent` is stubbed to raise, which is what makes these tests about money
rather than status codes: nothing billable runs on any rejected path. Note it
has to be `run_agent` and not the LLM dependency -- FastAPI resolves every
dependency before the endpoint body, even on a request it is about to reject
with a 422, so `get_llm_client` being reached proves nothing. Resolving it
just hands back a cached client; only `run_agent` spends tokens.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import predict as predict_module
from app.config import get_settings
from app.deps import get_llm_client, get_session
from app.main import app
from app.security import CLIENT_IP_HEADER, PROXY_SECRET_HEADER, limiter

SECRET = "test-proxy-secret"


def _no_session() -> Iterator[None]:
    yield None


def _stub_llm() -> object:
    """Stand-in client. Resolving it is free; running the agent is not."""
    return object()


def _must_not_run(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("the agent loop ran -- that request would have cost tokens")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client whose requests look like they came through the web proxy."""
    # verify_proxy reads settings directly rather than by injection, and
    # get_settings is lru_cached -- so set the env and clear the cache.
    monkeypatch.setenv("PROXY_SECRET", SECRET)
    get_settings.cache_clear()

    # Nothing fitted => 503 before the agent loop, so no DB and no API key.
    monkeypatch.setattr(predict_module, "latest_run_id", lambda _session: None)
    monkeypatch.setattr(predict_module, "run_agent", _must_not_run)
    monkeypatch.setattr(predict_module, "run_agent_events", _must_not_run)
    app.dependency_overrides[get_session] = _no_session
    app.dependency_overrides[get_llm_client] = _stub_llm
    limiter.reset()

    with TestClient(app) as c:
        c.headers.update({PROXY_SECRET_HEADER: SECRET})
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _body(query: str = "Will Bayern beat Dortmund?") -> dict[str, object]:
    return {"query": query}


def test_query_over_cap_is_rejected(client: TestClient) -> None:
    """A 501-char query fails validation, so it's never sent to the model."""
    resp = client.post("/predict", json=_body("x" * 501), headers={CLIENT_IP_HEADER: "10.0.0.1"})
    assert resp.status_code == 422
    assert "query" in str(resp.json()["detail"])


def test_query_at_cap_passes_validation(client: TestClient) -> None:
    """500 chars is allowed -- the cap is inclusive, not off by one.

    503 is the stubbed "nothing fitted" path, i.e. it got past validation,
    the proxy guard, and the rate limiter.
    """
    resp = client.post("/predict", json=_body("x" * 500), headers={CLIENT_IP_HEADER: "10.0.0.2"})
    assert resp.status_code == 503


def test_oversized_history_turn_is_rejected(client: TestClient) -> None:
    """History is the obvious way around the query cap, so it's capped too."""
    resp = client.post(
        "/predict",
        json={"query": "hi", "history": [{"role": "user", "content": "x" * 4001}]},
        headers={CLIENT_IP_HEADER: "10.0.0.3"},
    )
    assert resp.status_code == 422


def test_direct_call_without_proxy_secret_is_forbidden(client: TestClient) -> None:
    """Knowing the API's URL is not enough to drive it."""
    resp = client.post("/predict", json=_body(), headers={PROXY_SECRET_HEADER: ""})
    assert resp.status_code == 403


def test_wrong_proxy_secret_is_forbidden(client: TestClient) -> None:
    resp = client.post("/predict", json=_body(), headers={PROXY_SECRET_HEADER: "nope"})
    assert resp.status_code == 403


def test_stream_endpoint_is_guarded_too(client: TestClient) -> None:
    """Both endpoints run the agent, so both need the guard."""
    resp = client.post("/predict/stream", json=_body(), headers={PROXY_SECRET_HEADER: "nope"})
    assert resp.status_code == 403


def test_health_needs_no_proxy_secret() -> None:
    """The guard is on the router, so the health probe must stay reachable."""
    assert TestClient(app).get("/health").status_code == 200


def test_rate_limit_trips_on_the_eleventh_call(client: TestClient) -> None:
    """Ten per hour per caller; the eleventh gets a 429."""
    headers = {CLIENT_IP_HEADER: "203.0.113.7"}
    for _ in range(10):
        assert client.post("/predict", json=_body(), headers=headers).status_code == 503
    resp = client.post("/predict", json=_body(), headers=headers)
    assert resp.status_code == 429


def test_rate_limit_is_per_client_not_per_proxy(client: TestClient) -> None:
    """The whole point of forwarding the caller's address.

    Every request reaches the API from the same proxy, so limiting on the
    connecting address would let one heavy user lock out everyone else.
    """
    exhausted = {CLIENT_IP_HEADER: "203.0.113.8"}
    for _ in range(10):
        client.post("/predict", json=_body(), headers=exhausted)
    assert client.post("/predict", json=_body(), headers=exhausted).status_code == 429

    other = {CLIENT_IP_HEADER: "203.0.113.9"}
    assert client.post("/predict", json=_body(), headers=other).status_code == 503
