"""Column types the adopted tables need that Django has no built-in field for."""

from __future__ import annotations

import json
from typing import Any

from django.db import models
from django.db.models import Func
from django.db.models.expressions import RawSQL

# `now()` as the adopted tables define their defaults; Django's own `Now` renders
# `STATEMENT_TIMESTAMP()`.
DB_NOW = Func(function="now", output_field=models.DateTimeField())


class NaiveDateTimeField(models.DateTimeField):  # type: ignore[type-arg]
    """`timestamp without time zone`, which the tables had before Django took them over.

    Only the initial migrations reference it; a later migration moves every use to `timestamptz`.
    """

    def db_type(self, connection: Any) -> str:
        return "timestamp without time zone"


class PlainJSONField(models.JSONField):
    """JSON stored as `json` instead of `jsonb`, as `predictions.adjustments_json` was created.

    Django's JSON field expects psycopg to hand back `jsonb` as text and parses it itself. For a
    `json` column psycopg parses it first, so the value is read back as text (`::text`, which also
    keeps the stored document untouched) and written as a plain string to avoid a `jsonb` detour
    that would reorder keys.
    """

    def db_type(self, connection: Any) -> str:
        return "json"

    def get_db_prep_value(self, value: Any, connection: Any, prepared: bool = False) -> Any:
        if not prepared:
            value = self.get_prep_value(value)
        if value is None:
            return None
        return json.dumps(value, cls=self.encoder)

    def select_format(self, compiler: Any, sql: str, params: Any) -> tuple[str, Any]:
        return f"({sql})::text", params


# The adopted float defaults are the literal '0', which Postgres keeps as '0'::double precision.
FLOAT_ZERO = RawSQL("'0'", (), output_field=models.FloatField())
