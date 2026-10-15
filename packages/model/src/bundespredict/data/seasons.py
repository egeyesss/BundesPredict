"""Season-code helpers shared by the downloaders and the commands that call them."""

from __future__ import annotations

from datetime import date


def season_code(start_year: int) -> str:
    """2026 -> "2627", matching the season codes stored on matches and fixtures."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def results_season_start(today: date) -> int:
    """Start year of the season whose results are still arriving.

    Bundesliga seasons start in August; before that we are still in last year's.
    """
    return today.year if today.month >= 8 else today.year - 1


def schedule_season_start(today: date) -> int:
    """Start year of the season whose schedule matters now.

    From June on the summer gap belongs to the upcoming season (its schedule is what "next
    game" means); before June it is the season already running.
    """
    return today.year if today.month >= 6 else today.year - 1
