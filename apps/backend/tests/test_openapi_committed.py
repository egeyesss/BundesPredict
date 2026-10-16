from __future__ import annotations

from pathlib import Path

from django.core.management import call_command

COMMITTED = Path(__file__).resolve().parents[1] / "openapi.json"
REGENERATE = (
    "uv run apps/backend/manage.py spectacular --format openapi-json "
    "--file apps/backend/openapi.json"
)


def test_committed_openapi_matches_the_code(tmp_path: Path) -> None:
    generated = tmp_path / "openapi.json"

    call_command("spectacular", "--format", "openapi-json", file=str(generated))

    assert COMMITTED.read_text() == generated.read_text(), f"stale schema, run: {REGENERATE}"


def test_generation_is_deterministic(tmp_path: Path) -> None:
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    call_command("spectacular", "--format", "openapi-json", file=str(first))
    call_command("spectacular", "--format", "openapi-json", file=str(second))

    assert first.read_text() == second.read_text()
