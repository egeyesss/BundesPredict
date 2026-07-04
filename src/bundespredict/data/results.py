"""League-wide result queries for the agent's grounding tools.

`form.py` answers "how is this team doing"; this module answers the league-level
questions — what the most recent completed matches were and how fresh the data
is. The freshness date also feeds the system prompt, so the agent can reason
about whether the league is mid-season or in a break instead of claiming it has
no calendar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from .models import Match, Team


@dataclass(frozen=True)
class ResultRow:
    """One completed match as the agent reports it."""

    date: date
    season: str
    home: str
    away: str
    home_goals: int
    away_goals: int


def latest_result_date(session: Session) -> date | None:
    """Date of the most recent completed match, or ``None`` on an empty DB."""
    return session.execute(select(Match.date).order_by(Match.date.desc()).limit(1)).scalar()


def recent_results(
    session: Session,
    *,
    as_of_date: date | None = None,
    n: int = 9,
) -> tuple[ResultRow, ...]:
    """The last ``n`` completed matches league-wide, newest first.

    ``n`` defaults to 9 — one full Bundesliga round. The same strictly-before
    ``as_of_date`` discipline as every other query: results for a prediction
    dated D never include D itself.
    """
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(
            Match.date,
            Match.season,
            home_team.name,
            away_team.name,
            Match.home_goals,
            Match.away_goals,
        )
        .join(home_team, home_team.id == Match.home_id)
        .join(away_team, away_team.id == Match.away_id)
        .order_by(Match.date.desc(), Match.id.desc())
        .limit(n)
    )
    if as_of_date is not None:
        stmt = stmt.where(Match.date < as_of_date)

    return tuple(
        ResultRow(
            date=r[0],
            season=r[1],
            home=r[2],
            away=r[3],
            home_goals=r[4],
            away_goals=r[5],
        )
        for r in session.execute(stmt).all()
    )
