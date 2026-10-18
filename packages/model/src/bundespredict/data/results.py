"""The league-wide result row the agent's grounding tools report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ResultRow:
    """One completed match as the agent reports it."""

    date: date
    season: str
    home: str
    away: str
    home_goals: int
    away_goals: int
