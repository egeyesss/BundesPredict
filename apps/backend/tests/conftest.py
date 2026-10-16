"""Real Postgres for the Django tests, started once per session via testcontainers."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

# Same reasoning as the root conftest: the context manager already stops the container,
# and the Ryuk reaper image needs Docker Hub access that sandboxed runs may not have.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.management import call_command  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402
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


@pytest.fixture
def api_client() -> APIClient:
    """A DRF client that already carries the proxy secret, like the Next.js proxy does."""
    client = APIClient()
    client.credentials(HTTP_X_PROXY_SECRET=settings.PROXY_SECRET)
    return client


@pytest.fixture
def signed_in_client(api_client: APIClient) -> APIClient:
    """The same client with a session user, without touching the database."""
    api_client.force_authenticate(user=User(id=1, username="reader", email="reader@example.com"))
    return api_client


@pytest.fixture
def results_csv_dir(tmp_path: Path) -> Path:
    """A private copy of three small synthetic seasons (six clubs, 90 matches) of D1 CSVs."""
    destination = tmp_path / "raw"
    shutil.copytree(Path(__file__).parent / "football" / "commands" / "results_csv", destination)
    return destination


@pytest.fixture
def loaded_results(results_csv_dir: Path) -> Path:
    call_command("ingest_results", raw_dir=str(results_csv_dir), verbosity=0)
    return results_csv_dir


@pytest.fixture
def run_command() -> Callable[..., str]:
    """Run a management command and return what it printed."""

    def run(name: str, **options: object) -> str:
        out = StringIO()
        call_command(name, stdout=out, **options)
        return out.getvalue().strip()

    return run


@pytest.fixture
def table_rows() -> Callable[[Any], list[tuple[object, ...]]]:
    """Every row of a table with its ids, so a no-op run can be proven by equality."""

    def rows(model: Any) -> list[tuple[object, ...]]:
        return list(model.objects.order_by("pk").values_list())

    return rows


@pytest.fixture
def today() -> date:
    """A date after the last synthetic match (2025-05) and inside the 2425 season window."""
    return date(2025, 6, 1)
