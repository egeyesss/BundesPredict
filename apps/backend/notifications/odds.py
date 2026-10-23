"""Rounds three outcome probabilities for display, the same way `lib/odds.ts` does on the site."""

from __future__ import annotations

import math
from dataclasses import dataclass

DRAW = 1


@dataclass(frozen=True)
class DisplayOdds:
    order: tuple[int, int, int]
    decimals: int
    units: tuple[int, int, int]
    text: tuple[str, str, str]
    roles: tuple[str, str, str]
    lead: int


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _rank(probs: tuple[float, float, float], xg: tuple[float, float]) -> tuple[int, int, int]:
    favourite_team_on_tie = 0 if xg[0] >= xg[1] else 2

    def tie_break(index: int) -> tuple[float, int, int]:
        return (
            -probs[index],
            1 if index == DRAW else 0,
            0 if index == favourite_team_on_tie else 1,
        )

    first, second, third = sorted((0, 1, 2), key=tie_break)
    return first, second, third


def _largest_remainder(
    probs: tuple[float, float, float], decimals: int, order: tuple[int, int, int]
) -> list[int]:
    total = 100 * 10**decimals
    scaled = [_round_half_up(p * total * 1e6) / 1e6 for p in probs]
    floors = [math.floor(value) for value in scaled]
    left = total - sum(floors)
    by_remainder = sorted((0, 1, 2), key=lambda i: (-(scaled[i] - floors[i]), order.index(i)))
    for index in by_remainder:
        if left > 0:
            floors[index] += 1
        left -= 1
    return floors


def _text(unit: int, decimals: int) -> str:
    if unit == 0:
        return f"<{1 / 10**decimals:.{decimals}f}" if decimals else "<1"
    return f"{unit / 10**decimals:.{decimals}f}"


def display_odds(probs: tuple[float, float, float], xg: tuple[float, float]) -> DisplayOdds:
    """Fewest decimals (0 to 2) that keep the three values distinct, summing to exactly 100."""
    order = _rank(probs, xg)

    def distinct(units: list[int]) -> bool:
        return units[order[0]] > units[order[1]] > units[order[2]]

    chosen: list[int] | None = None
    decimals = 2
    for candidate in (0, 1, 2):
        units = _largest_remainder(probs, candidate, order)
        if distinct(units):
            chosen, decimals = units, candidate
            break

    if chosen is None:
        chosen = _largest_remainder(probs, 2, order)
        for rank in (1, 2):
            if chosen[order[rank]] >= chosen[order[rank - 1]]:
                chosen[order[rank]] = chosen[order[rank - 1]] - 1
        chosen[order[0]] += 10000 - sum(chosen)

    favourite_team = next(index for index in order if index != DRAW)
    roles = tuple(
        "draw" if index == DRAW else "win" if index == favourite_team else "lose"
        for index in (0, 1, 2)
    )
    units3 = (chosen[0], chosen[1], chosen[2])
    return DisplayOdds(
        order=order,
        decimals=decimals,
        units=units3,
        text=(_text(units3[0], decimals), _text(units3[1], decimals), _text(units3[2], decimals)),
        roles=(roles[0], roles[1], roles[2]),
        lead=order[0],
    )
