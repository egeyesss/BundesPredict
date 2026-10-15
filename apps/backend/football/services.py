"""Turns fixtures and the newest model run into the API's fixture cards."""

from __future__ import annotations

from typing import Any

import numpy as np

from bundespredict.model.dixon_coles import TeamRatings

from .models import Fixture, ModelRun, Team
from .repositories import team_params_for
from .serializers import markets_payload


def ratings_for(run: ModelRun) -> TeamRatings:
    """The run's stored parameters as the engine's `TeamRatings`, teams sorted by name."""
    params = team_params_for(run)
    return TeamRatings(
        teams=tuple(p.team.name for p in params),
        attack=np.array([p.attack for p in params], dtype=np.float64),
        defense=np.array([p.defense for p in params], dtype=np.float64),
        home_adv=run.home_adv,
        rho=run.rho,
        log_likelihood=run.log_likelihood,
        xg_coef=run.xg_coef,
    )


def team_payload(team: Team) -> dict[str, Any]:
    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name or team.name,
        "code": team.code,
        "crest": f"/crests/{team.code}.svg" if team.code else None,
    }


def fixture_card(
    fixture: Fixture, run: ModelRun, ratings: TeamRatings, *, with_markets: bool = False
) -> dict[str, Any] | None:
    """The card for one fixture, or `None` when the run cannot price it.

    A fixture is unpriceable when either club has no code (it has no crest identity) or no
    parameters in the run, which happens for a newly promoted side the last refit never saw.
    """
    home, away = fixture.home, fixture.away
    if not home.code or not away.code:
        return None
    if home.name not in ratings.teams or away.name not in ratings.teams:
        return None

    markets = markets_payload(ratings.predict(home.name, away.name))
    card: dict[str, Any] = {
        "id": fixture.id,
        "season": fixture.season,
        "matchday": fixture.matchday,
        "kickoff_utc": fixture.kickoff_utc,
        "home": team_payload(home),
        "away": team_payload(away),
        "base": {
            key: markets[key]
            for key in ("p_home", "p_draw", "p_away", "exp_home_goals", "exp_away_goals")
        },
        "model_run_id": run.id,
    }
    if with_markets:
        card["markets"] = markets
    return card
