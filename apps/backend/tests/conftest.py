"""Real Postgres for the Django tests, started once per session via testcontainers."""

from __future__ import annotations

import os
from collections.abc import Iterator

# Same reasoning as the root conftest: the context manager already stops the container,
# and the Ryuk reaper image needs Docker Hub access that sandboxed runs may not have.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest  # noqa: E402
from django.conf import settings  # noqa: E402
from testcontainers.community.postgres import PostgresContainer  # noqa: E402

# Keep in step with the db service in infra/docker-compose.yml.
POSTGRES_IMAGE = "postgres:17"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer(POSTGRES_IMAGE, driver=None) as postgres:
        yield postgres


@pytest.fixture(scope="session")
def django_db_modify_db_settings(postgres_container: PostgresContainer) -> None:
    settings.DATABASES["default"].update(
        {
            "NAME": postgres_container.dbname,
            "USER": postgres_container.username,
            "PASSWORD": postgres_container.password,
            "HOST": postgres_container.get_container_host_ip(),
            "PORT": postgres_container.get_exposed_port(5432),
        }
    )
