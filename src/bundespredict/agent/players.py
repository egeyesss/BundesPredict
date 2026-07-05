"""Player data for the agent's ``lookup_player`` tool.

The live lookup runs against the ``players`` table (the Transfermarkt scrape);
this module holds what stays in the agent package: the ``PlayerInfo`` shape the
tool returns, the seeded-JSON fallback used offline and in tests, and the
penalty-taker overlay. Penalty duty isn't on Transfermarkt, so it remains a
small curated list — the seeded JSON — merged onto whatever source answered
the lookup. An unknown name returns ``None`` (the agent then falls back to the
knowledge-base ranges rather than inventing a player).
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from importlib import resources
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bundespredict.data.players import normalize_name

Importance = Literal["high", "medium", "low"]


class PlayerInfo(BaseModel):
    """What the agent needs to size a player-availability adjustment.

    ``market_value_eur`` and ``scraped_at`` are set when the answer came from
    the scraped squad table; the seeded fallback leaves them ``None``.
    ``scraped_at`` is surfaced so a stale snapshot is visible, not trusted.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    team: str
    role: str
    is_penalty_taker: bool
    importance: Importance
    market_value_eur: int | None = None
    scraped_at: datetime | None = None


@lru_cache(maxsize=1)
def _seeded() -> list[PlayerInfo]:
    raw = resources.files("bundespredict.agent").joinpath("players.json").read_text()
    return [PlayerInfo(**row) for row in json.loads(raw)["players"]]


@lru_cache(maxsize=1)
def _index() -> dict[str, PlayerInfo]:
    """Build the lookup index keyed by normalized full name and last name.

    Last-name keys collide rarely in this small seed; when they do, the first
    seeded player wins, which is fine for a grounding hint. Full-name keys always
    take priority because they're tried first in :func:`lookup_player`.
    """
    by_name: dict[str, PlayerInfo] = {}
    for player in _seeded():
        by_name[normalize_name(player.name)] = player
    # Add last-name fallbacks without overwriting a full-name match.
    for player in _seeded():
        last = normalize_name(player.name.split()[-1])
        by_name.setdefault(last, player)
    return by_name


@lru_cache(maxsize=1)
def penalty_takers() -> frozenset[str]:
    """Normalized names of the curated penalty takers (the seeded JSON)."""
    return frozenset(normalize_name(p.name) for p in _seeded() if p.is_penalty_taker)


def lookup_player(name: str) -> PlayerInfo | None:
    """Find a seeded player by full name or last name; ``None`` if unknown.

    Matching is accent- and case-insensitive. Full name is tried first, then the
    last name, so "Kane" resolves but a full-name query is never shadowed by a
    last-name collision.
    """
    index = _index()
    key = normalize_name(name)
    if key in index:
        return index[key]
    last = normalize_name(name.split()[-1]) if name.split() else key
    return index.get(last)
