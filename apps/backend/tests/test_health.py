from __future__ import annotations

import pytest
from django.db import OperationalError, connection
from django.test import Client


@pytest.mark.django_db
def test_health_reports_database_and_no_model_run_yet(client: Client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_run_id": None, "db": "ok"}


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
