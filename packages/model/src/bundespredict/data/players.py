"""Player lookup over the scraped squad table.

The Transfermarkt scrape fills a ``players`` table (the caller's storage); this module
answers "who is X?" for the agent from rows the caller lists. Lookup is accent- and
case-insensitive, full name first, then last name. Importance is *derived*, not
hand-labelled: a player's standing by market value within his own squad (top ~20% ->
"high", next ~30% -> "medium", rest "low"). That rule lives here so the tool description
and the data can't drift apart.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# Market-value percentile cutoffs within a squad. Full kader pages list ~40
# contracted players including youth, so "key" is the top ~20% (≈ the first-XI
# core — a strict decile of 40 is 4 players and calls a €60m striker "medium"),
# the next band is a regular starter, the rest are squad depth.
HIGH_PERCENTILE = 0.8
MEDIUM_PERCENTILE = 0.5


def normalize_name(name: str) -> str:
    """Casefold and strip accents so "Sesko" matches "Šeško"."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().strip()


@dataclass(frozen=True)
class DbPlayer:
    """A squad member as the lookup returns it, team name canonical."""

    name: str
    team: str
    position: str
    market_value_eur: int | None
    importance: Literal["high", "medium", "low"]  # value standing within squad
    scraped_at: datetime


def _importance(value: int | None, squad_values: list[int]) -> Literal["high", "medium", "low"]:
    """Value standing within the squad: top ~20% high, next ~30% medium."""
    if value is None or not squad_values:
        return "low"
    below = sum(1 for v in squad_values if v < value)
    percentile = below / len(squad_values)
    if percentile >= HIGH_PERCENTILE:
        return "high"
    if percentile >= MEDIUM_PERCENTILE:
        return "medium"
    return "low"


PlayerRow = tuple[str, str, str, int | None, datetime]
"""``(name, team, position, market_value_eur, scraped_at)`` for one squad member."""


def pick_player(rows: list[PlayerRow], query: str) -> DbPlayer | None:
    """The best match for ``query`` among ``rows``, which must be value-descending.

    Full-name matches always win; last-name matches are a fallback and, on a collision (two
    squads with a "Müller"), the more valuable player wins, being the likelier subject of a
    "X is out" claim. Returns ``None`` when ``rows`` is empty, so the caller can fall back to
    the seeded offline data. Any backend that can list the squad table can reuse the matching
    and the importance rule.
    """
    if not rows:
        return None

    values_by_team: dict[str, list[int]] = {}
    for _, team, _, value, _ in rows:
        if value is not None:
            values_by_team.setdefault(team, []).append(value)

    def to_player(row: PlayerRow) -> DbPlayer:
        name, team, position, value, scraped_at = row
        return DbPlayer(
            name=name,
            team=team,
            position=position,
            market_value_eur=value,
            importance=_importance(value, values_by_team.get(team, [])),
            scraped_at=scraped_at,
        )

    key = normalize_name(query)
    last_key = normalize_name(query.split()[-1]) if query.split() else key
    last_match: DbPlayer | None = None
    for row in rows:  # value-descending, so the first last-name hit is the richest
        if normalize_name(row[0]) == key:
            return to_player(row)
        if last_match is None and normalize_name(row[0].split()[-1]) == last_key:
            last_match = to_player(row)
    return last_match
