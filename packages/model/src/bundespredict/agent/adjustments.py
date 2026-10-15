"""The typed adjustment object and its grounding knowledge base.

This is the agent layer's side of the contract with the engine. The LLM never
emits a probability; it emits :class:`Adjustment`s — bounded, typed nudges in
expected-goals space — and the pure engine
(:mod:`bundespredict.model.adjust`) turns them into a distribution. Splitting it
this way is the whole point: language understanding lives here, the math lives
there, and nothing the model says can move a probability except through a
clamped, audited delta.

The magnitude is intentionally *not* clamped at construction. We keep whatever
the LLM asked for so the audit trail shows the request, and the engine clamps it
to ``+/- MAGNITUDE_BOUND`` when it actually applies it. So a hallucinated
``+5.0`` is recorded faithfully and still only ever moves expected goals by 0.6.
"""

from __future__ import annotations

import math
from functools import lru_cache
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

# What kind of real-world thing the adjustment encodes — purely descriptive, used
# for grounding against the knowledge base and for the UI label.
Factor = Literal[
    "player_out",
    "player_in",
    "crowd",
    "motivation",
    "congestion",
    "weather_wind",
    "weather_rain",
    "weather_heat",
    "tactical",
    "referee_cards",
    "referee_penalty",
]

# What the adjustment modifies in the engine. These must match the engine's
# routing table exactly; a drift test pins that down.
Target = Literal[
    "home_attack",
    "home_defense",
    "away_attack",
    "away_defense",
    "home_adv",
    "cards_rate",
    "pen_rate",
]

Side = Literal["home", "away"]
Confidence = Literal["low", "med", "high"]


class Adjustment(BaseModel):
    """One bounded, typed nudge to the model's expected-goals inputs.

    Frozen and ``extra="forbid"`` so a malformed tool call from the LLM is
    rejected at validation rather than silently coerced. ``magnitude_xg`` carries
    its own sign (a key striker out is ``home_attack`` with a negative value); the
    engine clamps the magnitude when it applies it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor: Factor
    team: Side | None = None
    target: Target
    magnitude_xg: float
    confidence: Confidence
    rationale: str

    @field_validator("magnitude_xg")
    @classmethod
    def _finite(cls, value: float) -> float:
        # Bounds are the engine's job (it clamps); we only reject NaN/inf, which
        # would otherwise poison the lambda arithmetic downstream.
        if not math.isfinite(value):
            raise ValueError("magnitude_xg must be a finite number")
        return value

    @field_validator("rationale")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rationale must not be empty — every adjustment is auditable")
        return value

    @property
    def is_disciplinary(self) -> bool:
        """True for cards/penalty targets, which never move the 1X2 result."""
        return self.target in {"cards_rate", "pen_rate"}

    def as_delta(self) -> tuple[str, float]:
        """The ``(target, magnitude)`` pair the engine apply-path consumes."""
        return self.target, self.magnitude_xg


class KBEntry(BaseModel):
    """One grounding row from ``adjustments.yaml``.

    ``min_xg`` / ``max_xg`` bracket the magnitude the agent should pick *within*;
    ``source`` is mandatory and is either a citation or the literal ``heuristic``
    — no unsourced numbers dressed up as research.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    factor: Factor
    target: Target
    min_xg: float
    max_xg: float
    source: str
    note: str


@lru_cache(maxsize=1)
def load_kb() -> tuple[KBEntry, ...]:
    """Load and validate the magnitude knowledge base shipped beside this module.

    Cached: the file is small and read-only at serve time. Each row is validated
    through :class:`KBEntry`, so a malformed or unsourced entry fails loudly here
    rather than feeding the agent a bad range.
    """
    raw = resources.files("bundespredict.agent").joinpath("adjustments.yaml").read_text()
    data = yaml.safe_load(raw)
    entries = tuple(KBEntry(**row) for row in data["factors"])
    return entries
