"""Tests for the agent's temporal grounding: date context, results, fixtures.

These are the guards against the "I don't have access to a calendar" failure
mode: the system prompt must carry today's date and data freshness, and the
two league-level tools must answer from the database.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
from sqlalchemy.orm import Session

from bundespredict.agent.prompt import build_system_prompt
from bundespredict.agent.service import GroundingContext, PredictionService
from bundespredict.agent.tools import dispatch
from bundespredict.data.fixtures import FixtureRow, ingest_fixtures
from bundespredict.data.models import Match, Team
from bundespredict.model.dixon_coles import TeamRatings

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"


def _ratings() -> TeamRatings:
    return TeamRatings(
        teams=(HOME, AWAY),
        attack=np.array([0.4, -0.4]),
        defense=np.array([-0.2, 0.2]),
        home_adv=0.3,
        rho=-0.12,
        log_likelihood=0.0,
    )


def _seed(session: Session) -> None:
    dortmund = Team(name=HOME)
    leipzig = Team(name=AWAY)
    session.add_all([dortmund, leipzig])
    session.flush()
    session.add(
        Match(
            season="2526",
            date=date(2026, 5, 16),
            home_id=dortmund.id,
            away_id=leipzig.id,
            home_goals=2,
            away_goals=0,
            ftr="H",
        )
    )
    session.commit()
    ingest_fixtures(
        session,
        [
            FixtureRow(
                season="2627",
                matchday=1,
                kickoff_utc=datetime(2026, 8, 29, 13, 30),
                home="Borussia Dortmund",
                away="Hamburger SV",
            )
        ],
    )


def test_context_reports_today_and_data_freshness(session: Session) -> None:
    _seed(session)
    service = PredictionService(_ratings(), session=session, as_of_date=date(2026, 7, 4))
    assert service.context == GroundingContext(
        today=date(2026, 7, 4), data_through=date(2026, 5, 16)
    )


def test_prompt_carries_dates_and_the_break_hint() -> None:
    context = GroundingContext(today=date(2026, 7, 4), data_through=date(2026, 5, 16))
    prompt = build_system_prompt((HOME, AWAY), context)
    assert "2026-07-04" in prompt
    assert "2026-05-16" in prompt
    # 49 days since the last result -> the prompt states the league is in a break.
    assert "break" in prompt

    mid_season = GroundingContext(today=date(2026, 5, 17), data_through=date(2026, 5, 16))
    assert "break" not in build_system_prompt((HOME, AWAY), mid_season)


def test_dispatch_recent_results(session: Session) -> None:
    _seed(session)
    service = PredictionService(_ratings(), session=session, as_of_date=date(2026, 7, 4))
    out = dispatch("get_recent_results", {"n": 5}, service)
    assert not out.is_error
    assert out.payload["results"][0] == {
        "date": "2026-05-16",
        "home": HOME,
        "away": AWAY,
        "score": "2-0",
    }


def test_dispatch_upcoming_fixtures_resolves_the_next_game(session: Session) -> None:
    _seed(session)
    service = PredictionService(_ratings(), session=session, as_of_date=date(2026, 7, 4))
    out = dispatch("get_upcoming_fixtures", {"team": HOME}, service)
    assert not out.is_error
    fixture = out.payload["fixtures"][0]
    assert fixture["home"] == HOME
    assert fixture["away"] == "Hamburger SV"
    assert fixture["matchday"] == 1
    assert fixture["kickoff_utc"] == "2026-08-29T13:30:00Z"


def test_dispatch_upcoming_fixtures_empty_when_no_schedule(session: Session) -> None:
    _seed(session)
    # A service dated after the only stored kickoff sees an empty schedule.
    service = PredictionService(_ratings(), session=session, as_of_date=date(2026, 9, 1))
    out = dispatch("get_upcoming_fixtures", {}, service)
    assert not out.is_error
    assert out.payload["fixtures"] == []


def test_dispatch_upcoming_fixtures_unknown_team_is_recoverable(session: Session) -> None:
    _seed(session)
    service = PredictionService(_ratings(), session=session, as_of_date=date(2026, 7, 4))
    out = dispatch("get_upcoming_fixtures", {"team": "Atlantis FC"}, service)
    assert out.is_error
