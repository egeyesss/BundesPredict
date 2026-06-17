"""Seeded player lookup for the agent's ``lookup_player`` tool.

The plan grounds player magnitudes in a cached Transfermarkt scrape, but that's
deferred to the enrichment phase. So the tool reads a small hand-seeded JSON
instead: enough notable players that the tool exists, the agent can ground a
"striker out" claim against a real role/importance, and the path is testable —
clearly a seed, not a roster. An unknown name returns ``None`` (the agent then
falls back to the knowledge-base ranges rather than inventing a player).
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from importlib import resources
from typing import Literal

from pydantic import BaseModel, ConfigDict

Importance = Literal["high", "medium", "low"]


class PlayerInfo(BaseModel):
    """What the agent needs to size a player-availability adjustment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    team: str
    role: str
    is_penalty_taker: bool
    importance: Importance


def _normalize(name: str) -> str:
    """Casefold and strip accents so "Sesko" matches "Šeško"."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().strip()


@lru_cache(maxsize=1)
def _index() -> dict[str, PlayerInfo]:
    """Build the lookup index keyed by normalized full name and last name.

    Last-name keys collide rarely in this small seed; when they do, the first
    seeded player wins, which is fine for a grounding hint. Full-name keys always
    take priority because they're tried first in :func:`lookup_player`.
    """
    raw = resources.files("bundespredict.agent").joinpath("players.json").read_text()
    players = [PlayerInfo(**row) for row in json.loads(raw)["players"]]

    by_name: dict[str, PlayerInfo] = {}
    for player in players:
        by_name[_normalize(player.name)] = player
    # Add last-name fallbacks without overwriting a full-name match.
    for player in players:
        last = _normalize(player.name.split()[-1])
        by_name.setdefault(last, player)
    return by_name


def lookup_player(name: str) -> PlayerInfo | None:
    """Find a seeded player by full name or last name; ``None`` if unknown.

    Matching is accent- and case-insensitive. Full name is tried first, then the
    last name, so "Kane" resolves but a full-name query is never shadowed by a
    last-name collision.
    """
    index = _index()
    key = _normalize(name)
    if key in index:
        return index[key]
    last = _normalize(name.split()[-1]) if name.split() else key
    return index.get(last)
