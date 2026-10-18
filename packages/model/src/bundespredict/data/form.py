"""Recent-form shapes for the agent's ``get_team_form`` tool.

The agent uses these to ground claims ("they've won four on the bounce") against
actual results instead of guessing. Whatever builds a :class:`TeamForm` carries the
leakage discipline: results are restricted to matches played **strictly before** the
prediction date, so form for a fixture on date D never includes D itself or anything
later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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
