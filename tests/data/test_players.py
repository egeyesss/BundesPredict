"""Player matching and the value-derived importance rule, over rows a store would list."""

from __future__ import annotations

from datetime import datetime

from bundespredict.data.players import PlayerRow, normalize_name, pick_player

SCRAPED = datetime(2026, 7, 5, 8, 0)


def _squad(
    team: str, values: list[int | None], *, first_name: str | None = None
) -> list[PlayerRow]:
    return [
        (
            first_name if index == 0 and first_name else f"{team} Player {index}",
            team,
            "Midfield",
            value,
            SCRAPED,
        )
        for index, value in enumerate(values)
    ]


def _richest_first(rows: list[PlayerRow]) -> list[PlayerRow]:
    return sorted(rows, key=lambda row: row[3] is not None and row[3] or -1, reverse=True)


def test_normalize_name_strips_accents_and_case() -> None:
    assert normalize_name("  Benjamín Šeško ") == "benjamin sesko"


def test_accent_insensitive_match_carries_team_importance_and_snapshot_age() -> None:
    values: list[int | None] = [
        50_000_000,
        *([20_000_000] * 8),
        *([5_000_000] * 6),
        *([500_000] * 5),
    ]
    rows = _richest_first(_squad("RB Leipzig", values, first_name="Benjamín Šeško"))

    found = pick_player(rows, "benjamin sesko")
    assert found is not None
    assert found.team == "RB Leipzig"
    assert found.importance == "high"  # top of the squad by value
    assert found.scraped_at == SCRAPED

    by_last_name = pick_player(rows, "Sesko")
    assert by_last_name is not None and by_last_name.name == "Benjamín Šeško"


def test_importance_bands_follow_value_standing_within_the_squad() -> None:
    values: list[int | None] = [value * 1_000_000 for value in range(20, 0, -1)]
    rows = _squad("RB Leipzig", values)

    def importance(index: int) -> str | None:
        found = pick_player(rows, f"RB Leipzig Player {index}")
        return found.importance if found else None

    # 16 of 20 squad members below him is the 0.8 cut for "high"; 10 of 20 is the 0.5 cut.
    assert [importance(index) for index in (0, 3, 4, 9, 10)] == [
        "high",
        "high",
        "medium",
        "medium",
        "low",
    ]


def test_a_player_without_a_value_is_low_importance() -> None:
    rows = _squad("RB Leipzig", [5_000_000, 1_000_000, None])

    found = pick_player(rows, "RB Leipzig Player 2")
    assert found is not None and found.importance == "low"


def test_an_unknown_name_is_none() -> None:
    rows = _squad("RB Leipzig", [1_000_000, 2_000_000])

    assert pick_player(rows, "Erling Haaland") is None


def test_a_last_name_collision_prefers_the_higher_value() -> None:
    rows = _richest_first(
        [
            ("Thomas Müller", "Bayern Munich", "Second Striker", 9_000_000, SCRAPED),
            ("Kevin Müller", "1.FC Heidenheim 1846", "Goalkeeper", 300_000, SCRAPED),
        ]
    )

    found = pick_player(rows, "Müller")
    assert found is not None and found.name == "Thomas Müller"


def test_a_full_name_beats_a_richer_last_name_match() -> None:
    rows = _richest_first(
        [
            ("Thomas Müller", "Bayern Munich", "Second Striker", 9_000_000, SCRAPED),
            ("Kevin Müller", "1.FC Heidenheim 1846", "Goalkeeper", 300_000, SCRAPED),
        ]
    )

    found = pick_player(rows, "Kevin Müller")
    assert found is not None and found.team == "1.FC Heidenheim 1846"


def test_an_empty_table_is_none() -> None:
    assert pick_player([], "anyone") is None
