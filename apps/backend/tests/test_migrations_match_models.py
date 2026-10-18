from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_every_model_change_has_a_migration() -> None:
    out = StringIO()

    call_command("makemigrations", check=True, dry_run=True, stdout=out)

    assert "No changes detected" in out.getvalue()
