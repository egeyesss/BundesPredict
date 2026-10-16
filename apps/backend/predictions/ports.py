"""The agent's ports backed by the Django ORM.

Every method is synchronous and touches the database, so an async caller runs the whole agent
step through `sync_to_async` rather than awaiting individual ports.
"""

from __future__ import annotations

from datetime import date

from bundespredict.agent.ports import ServingRun
from bundespredict.agent.service import PredictionRecord
from bundespredict.agent.tools import _applied_adjustment
from bundespredict.data.fixtures import UpcomingFixture
from bundespredict.data.form import TeamForm
from bundespredict.data.players import DbPlayer, pick_player
from bundespredict.data.results import ResultRow
from football import repositories
from football.models import Team

from .models import Prediction

SERVING_VERSION = "serve"


class DjangoAgentPorts:
    """Satisfies the agent's data, params and persistence protocols through the ORM."""

    def latest_ratings(self) -> ServingRun | None:
        run = repositories.latest_model_run(version=SERVING_VERSION)
        if run is None:
            return None
        return ServingRun(run_id=run.id, ratings=repositories.ratings_for(run))

    def team_form(self, team: str, *, as_of_date: date | None, n: int) -> TeamForm:
        return repositories.team_form(_team_named(team), as_of_date, n=n)

    def latest_result_date(self) -> date | None:
        return repositories.latest_result_date()

    def recent_results(self, *, as_of_date: date | None, n: int) -> tuple[ResultRow, ...]:
        return repositories.recent_results(as_of_date, n=n)

    def find_player(self, query: str) -> DbPlayer | None:
        return pick_player(repositories.player_rows(), query)

    def upcoming_fixtures(
        self, *, team: str | None, on_or_after: date, n: int
    ) -> tuple[UpcomingFixture, ...]:
        club = _team_named(team) if team is not None else None
        return repositories.scheduled_fixtures(on_or_after, team=club, n=n)

    def save(
        self,
        *,
        model_run_id: int,
        record: PredictionRecord,
        explanation: str | None,
        query: str | None,
        match_date: date | None,
    ) -> int:
        ids = dict(
            Team.objects.filter(name__in=[record.home, record.away]).values_list("name", "id")
        )
        missing = {record.home, record.away} - ids.keys()
        if missing:
            raise ValueError(f"no teams row for: {sorted(missing)}")

        served, baseline = record.served, record.baseline
        prediction = Prediction.objects.create(
            model_run_id=model_run_id,
            home_id=ids[record.home],
            away_id=ids[record.away],
            match_date=match_date,
            query=query,
            p_home=served.p_home,
            p_draw=served.p_draw,
            p_away=served.p_away,
            exp_home_goals=served.exp_home_goals,
            exp_away_goals=served.exp_away_goals,
            base_p_home=baseline.p_home,
            base_p_draw=baseline.p_draw,
            base_p_away=baseline.p_away,
            adjustments_json=[_applied_adjustment(a) for a in record.adjustments],
            explanation=explanation,
        )
        return prediction.id


def _team_named(name: str) -> Team:
    """The team with this canonical name; `ValueError` otherwise, like the SQLAlchemy path."""
    team = Team.objects.filter(name=name).first()
    if team is None:
        raise ValueError(f"unknown team: {name!r}")
    return team
