from __future__ import annotations

import pytest
from django.db import OperationalError, connection
from django.test import Client

from football.models import ModelRun


def _model_run(version: str) -> ModelRun:
    return ModelRun.objects.create(
        model_type="dixon_coles",
        version=version,
        xi=0.0018,
        rho=-0.12,
        home_adv=0.3,
        log_likelihood=-1.0,
        n_matches=100,
    )


@pytest.mark.django_db
def test_health_reports_database_and_no_model_run_yet(client: Client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_run_id": None, "db": "ok"}


@pytest.mark.django_db
def test_health_reports_the_serving_run_not_a_newer_backtest_run(client: Client) -> None:
    serving = _model_run("serve")
    _model_run("walk-forward")

    response = client.get("/api/v1/health")

    assert response.json() == {"status": "ok", "model_run_id": serving.pk, "db": "ok"}


@pytest.mark.django_db
def test_health_answers_503_when_the_database_is_unreachable(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse_connection(*args: object, **kwargs: object) -> None:
        raise OperationalError("connection refused")

    monkeypatch.setattr(connection, "cursor", refuse_connection)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "model_run_id": None, "db": "unavailable"}
