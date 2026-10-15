"""Recent-form lookup for the agent's ``get_team_form`` tool.

The agent uses this to ground claims ("they've won four on the bounce") against
actual results instead of guessing. Like the rest of the data layer it is the
seam between the database and the engine/agent, and it carries the same leakage
discipline: ``as_of_date`` restricts to matches played **strictly before** the
prediction date, so form for a fixture on date D never includes D itself or
anything later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Match, Team


@dataclass(frozen=True)
class FormMatch:
    """One past result from the team's perspective."""

    date: date
    opponent: str
    venue: str  # "H" if the team played at home, else "A"
    goals_for: int
    goals_against: int
    result: str  # "W" | "D" | "L"


@dataclass(frozen=True)
class TeamForm:
    """A team's recent results plus the aggregates the agent reasons over."""

    team: str
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    goals_for: int
    goals_against: int
    matches: tuple[FormMatch, ...]  # most recent first


def _result(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "W"
    if goals_for < goals_against:
        return "L"
    return "D"


def recent_form(
    session: Session,
    team: str,
    *,
    as_of_date: date | None = None,
    n: int = 5,
) -> TeamForm:
    """The team's last ``n`` results before ``as_of_date``, newest first.

    ``team`` is a canonical name. Raises ``ValueError`` if the name is unknown so
    a typo from the agent fails loudly rather than returning empty form. A team
    with no prior matches (e.g. a newcomer at season start) returns a zeroed
    :class:`TeamForm` — valid, just empty.
    """
    team_id = session.execute(select(Team.id).where(Team.name == team)).scalar_one_or_none()
    if team_id is None:
        raise ValueError(f"unknown team: {team!r}")

    stmt = (
        select(
            Match.date,
            Match.home_id,
            Match.away_id,
            Match.home_goals,
            Match.away_goals,
        )
        .where(or_(Match.home_id == team_id, Match.away_id == team_id))
        .order_by(Match.date.desc(), Match.id.desc())
        .limit(n)
    )
    if as_of_date is not None:
        stmt = stmt.where(Match.date < as_of_date)

    rows = session.execute(stmt).all()

    # Resolve opponent ids in the slice to names in one round trip.
    opp_ids = {(r.away_id if r.home_id == team_id else r.home_id) for r in rows}
    id_to_name: dict[int, str] = dict(
        session.execute(select(Team.id, Team.name).where(Team.id.in_(opp_ids))).tuples().all()
    )

    matches: list[FormMatch] = []
    wins = draws = losses = goals_for = goals_against = 0
    for r in rows:
        at_home = r.home_id == team_id
        gf = r.home_goals if at_home else r.away_goals
        ga = r.away_goals if at_home else r.home_goals
        outcome = _result(gf, ga)
        wins += outcome == "W"
        draws += outcome == "D"
        losses += outcome == "L"
        goals_for += gf
        goals_against += ga
        matches.append(
            FormMatch(
                date=r.date,
                opponent=id_to_name[r.away_id if at_home else r.home_id],
                venue="H" if at_home else "A",
                goals_for=gf,
                goals_against=ga,
                result=outcome,
            )
        )

    return TeamForm(
        team=team,
        played=len(matches),
        wins=wins,
        draws=draws,
        losses=losses,
        points=3 * wins + draws,
        goals_for=goals_for,
        goals_against=goals_against,
        matches=tuple(matches),
    )
