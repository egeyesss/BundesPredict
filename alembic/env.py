"""Alembic migration environment.

Connection URL and target metadata come from the application, not alembic.ini:
the URL is read from ``DATABASE_URL`` (normalized to psycopg3) and the schema is
``Base.metadata`` so autogenerate stays in sync with the ORM models.
"""

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import DateTime, engine_from_config, pool

from bundespredict.data.db import get_database_url
from bundespredict.data.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_database_url())
target_metadata = Base.metadata


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any | None
) -> bool:
    """Skip anything in the database that these models do not describe.

    Django owns the schema now and adds its own tables, plus columns and constraints on the
    adopted ones (`teams.code`), so `alembic check` must not read those as drift.
    """
    return not (reflected and compare_to is None)


def compare_type(
    context: Any,
    inspected_column: Any,
    metadata_column: Any,
    inspected_type: Any,
    metadata_type: Any,
) -> bool | None:
    """Ignore timezone-awareness: Django moved the naive UTC columns to `timestamptz`."""
    if isinstance(inspected_type, DateTime) and isinstance(metadata_type, DateTime):
        return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
