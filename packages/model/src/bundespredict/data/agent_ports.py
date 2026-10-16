"""The agent's ports backed by one SQLAlchemy session (the FastAPI app's data path)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from bundespredict.agent.ports import ServingRun
from bundespredict.agent.service import PredictionRecord

from .fixtures import UpcomingFixture, upcoming_fixtures
from .form import TeamForm, recent_form
from .params_store import latest_run_id, load_ratings
from .players import DbPlayer, find_player
from .predictions_store import save_prediction
from .results import ResultRow, latest_result_date, recent_results


class SqlAlchemyPorts:
    """Satisfies the agent's data, params and persistence protocols over ``session``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_ratings(self) -> ServingRun | None:
        run_id = latest_run_id(self._session)
        if run_id is None:
            return None
        return ServingRun(run_id=run_id, ratings=load_ratings(self._session, run_id))

    def team_form(self, team: str, *, as_of_date: date | None, n: int) -> TeamForm:
        return recent_form(self._session, team, as_of_date=as_of_date, n=n)

    def latest_result_date(self) -> date | None:
        return latest_result_date(self._session)

    def recent_results(self, *, as_of_date: date | None, n: int) -> tuple[ResultRow, ...]:
        return recent_results(self._session, as_of_date=as_of_date, n=n)

    def find_player(self, query: str) -> DbPlayer | None:
        return find_player(self._session, query)

    def upcoming_fixtures(
        self, *, team: str | None, on_or_after: date, n: int
    ) -> tuple[UpcomingFixture, ...]:
        return upcoming_fixtures(self._session, team=team, on_or_after=on_or_after, n=n)

    def save(
        self,
        *,
        model_run_id: int,
        record: PredictionRecord,
        explanation: str | None,
        query: str | None,
        match_date: date | None,
    ) -> int:
        return save_prediction(
            self._session,
            model_run_id=model_run_id,
            record=record,
            explanation=explanation,
            query=query,
            match_date=match_date,
        )
