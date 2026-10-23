"""The email rounds odds like the site's `displayOdds`, so a fixture reads the same in both."""

from __future__ import annotations

import pytest

from notifications.odds import display_odds

Triple = tuple[float, float, float]
Case = tuple[Triple, tuple[float, float], list[str], int, list[str], int]

# Same cases as apps/web/lib/odds.test.ts: probs, xg, text, decimals, roles, lead.
CASES: list[Case] = [
    ((0.6421, 0.1902, 0.1677), (2.61, 1.14), ["64", "19", "17"], 0, ["win", "draw", "lose"], 0),
    (
        (0.2618, 0.2544, 0.4838),
        (1.11, 1.74),
        ["26.2", "25.4", "48.4"],
        1,
        ["lose", "draw", "win"],
        2,
    ),
    (
        (0.3349, 0.3352, 0.3299),
        (1.18, 1.16),
        ["33.49", "33.52", "32.99"],
        2,
        ["win", "draw", "lose"],
        1,
    ),
    ((0.3645, 0.2712, 0.3643), (1.31, 1.3), ["37", "27", "36"], 0, ["win", "draw", "lose"], 0),
    ((0.38, 0.24, 0.38), (1.37, 1.42), ["37.99", "24.00", "38.01"], 2, ["lose", "draw", "win"], 2),
    ((0.38, 0.24, 0.38), (1.4, 1.4), ["38.01", "24.00", "37.99"], 2, ["win", "draw", "lose"], 0),
    (
        (0.33333, 0.33334, 0.33333),
        (1.2, 1.2),
        ["33.33", "33.35", "33.32"],
        2,
        ["win", "draw", "lose"],
        1,
    ),
    ((0.968, 0.028, 0.004), (3.1, 0.4), ["97", "3", "<1"], 0, ["win", "draw", "lose"], 0),
    ((0.335, 0.335, 0.33), (1.3, 1.25), ["33.51", "33.49", "33.00"], 2, ["win", "draw", "lose"], 0),
]


@pytest.mark.parametrize(("probs", "xg", "text", "decimals", "roles", "lead"), CASES)
def test_matches_the_site(
    probs: Triple,
    xg: tuple[float, float],
    text: list[str],
    decimals: int,
    roles: list[str],
    lead: int,
) -> None:
    odds = display_odds(probs, xg)

    assert list(odds.text) == text
    assert odds.decimals == decimals
    assert list(odds.roles) == roles
    assert odds.lead == lead


@pytest.mark.parametrize(("probs", "xg"), [(case[0], case[1]) for case in CASES])
def test_units_sum_to_exactly_one_hundred_percent_and_stay_distinct(
    probs: Triple, xg: tuple[float, float]
) -> None:
    odds = display_odds(probs, xg)

    assert sum(odds.units) == 100 * 10**odds.decimals
    assert len(set(odds.units)) == 3
