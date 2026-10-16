"""Every endpoint in the v1 contract table exists, with the right method, in the OpenAPI schema."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.management import call_command
from drf_spectacular.generators import SchemaGenerator

# (method, path as it appears in the schema)
CONTRACT: list[tuple[str, str]] = [
    ("get", "/api/v1/health"),
    ("get", "/api/v1/fixtures"),
    ("get", "/api/v1/fixtures/{id}"),
    ("get", "/api/v1/teams"),
    ("post", "/api/v1/predict/stream"),
    ("get", "/api/v1/me"),
    ("patch", "/api/v1/me"),
    ("get", "/api/v1/conversations"),
    ("get", "/api/v1/conversations/{id}"),
    ("delete", "/api/v1/conversations/{id}"),
    ("post", "/api/v1/billing/checkout"),
    ("post", "/api/v1/billing/portal"),
    ("get", "/api/v1/track-record"),
    ("get", "/api/v1/admin/metrics"),
    ("post", "/api/v1/demo/start"),
    ("post", "/api/v1/email/unsubscribe"),
    ("post", "/stripe/webhook/live"),
    ("post", "/stripe/webhook/test"),
]


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    generator = SchemaGenerator()  # type: ignore[no-untyped-call]
    return dict(generator.get_schema(request=None, public=True))  # type: ignore[no-untyped-call]


@pytest.mark.parametrize(("method", "path"), CONTRACT)
def test_contract_endpoint_is_in_the_schema(schema: dict[str, Any], method: str, path: str) -> None:
    assert method in schema["paths"].get(path, {})


def test_schema_has_no_endpoints_outside_the_contract(schema: dict[str, Any]) -> None:
    documented = {(m, p) for p, ops in schema["paths"].items() for m in ops}

    assert documented == set(CONTRACT)


def test_spectacular_validates_without_warnings(tmp_path: Any) -> None:
    call_command("spectacular", "--validate", "--fail-on-warn", file=str(tmp_path / "openapi.json"))


def test_stream_documents_event_stream_and_every_event_payload(schema: dict[str, Any]) -> None:
    operation = schema["paths"]["/api/v1/predict/stream"]["post"]
    content = operation["responses"]["200"]["content"]
    schemas = schema["components"]["schemas"]

    assert list(content) == ["text/event-stream"]
    frame_names = {
        "ConversationFrame",
        "QuotaFrame",
        "StageFrame",
        "ResultFrame",
        "ErrorFrame",
    }
    assert frame_names <= set(schemas)
    assert {"ToolCallStage", "ToolResultStage", "PredictResponse"} <= set(schemas)


def test_stream_documents_its_pre_stream_errors(schema: dict[str, Any]) -> None:
    responses = schema["paths"]["/api/v1/predict/stream"]["post"]["responses"]

    assert {"200", "400", "401", "402", "429", "503"} <= set(responses)


def test_session_endpoints_declare_cookie_auth_and_public_ones_do_not(
    schema: dict[str, Any],
) -> None:
    paths = schema["paths"]

    assert paths["/api/v1/me"]["get"]["security"] == [{"cookieAuth": []}]
    assert paths["/api/v1/teams"]["get"].get("security") in (None, [{}])
