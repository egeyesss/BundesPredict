"""The seams between the agent and whatever stores the data.

The agent never opens a database session. It asks these protocols for the facts it grounds claims
in (form, results, fixtures, players), for the serving ratings, and for somewhere to write the
audit row. The FastAPI app satisfies them through SQLAlchemy
(:class:`bundespredict.data.agent_ports.SqlAlchemyPorts`); the Django backend satisfies them
through its ORM.

All methods are synchronous. A caller on an event loop runs the whole agent step in a worker
thread rather than awaiting individual ports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from bundespredict.data.fixtures import UpcomingFixture
from bundespredict.data.form import TeamForm
from bundespredict.data.players import DbPlayer
from bundespredict.data.results import ResultRow
from bundespredict.model.dixon_coles import TeamRatings

if TYPE_CHECKING:
    from .service import PredictionRecord


@dataclass(frozen=True)
class ServingRun:
    """The fitted run answering requests: its id (for the audit row) and its ratings."""

    run_id: int
    ratings: TeamRatings


class ParamsPort(Protocol):
    def latest_ratings(self) -> ServingRun | None:
        """The newest serving fit, or ``None`` when nothing has been fitted yet."""
        ...


class FormPort(Protocol):
    def team_form(self, team: str, *, as_of_date: date | None, n: int) -> TeamForm:
        """The last ``n`` results before ``as_of_date``; ``ValueError`` for an unknown team."""
        ...


class ResultsPort(Protocol):
    def latest_result_date(self) -> date | None: ...

    def recent_results(self, *, as_of_date: date | None, n: int) -> tuple[ResultRow, ...]: ...


class PlayersPort(Protocol):
    def find_player(self, query: str) -> DbPlayer | None:
        """A squad member by full or last name, or ``None`` when unknown or the table is empty."""
        ...


class FixturesPort(Protocol):
    def upcoming_fixtures(
        self, *, team: str | None, on_or_after: date, n: int
    ) -> tuple[UpcomingFixture, ...]:
        """Scheduled fixtures from ``on_or_after`` on; ``ValueError`` for an unknown team."""
        ...


class AgentDataPorts(FormPort, ResultsPort, PlayersPort, FixturesPort, Protocol):
    """Everything :class:`~bundespredict.agent.service.PredictionService` reads."""


class PredictionStore(Protocol):
    def save(
        self,
        *,
        model_run_id: int,
        record: PredictionRecord,
        explanation: str | None,
        query: str | None,
        match_date: date | None,
    ) -> int:
        """Persist one audit row and return its id; ``ValueError`` for a team that is not stored."""
        ...
