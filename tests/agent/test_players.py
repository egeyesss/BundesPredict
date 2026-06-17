"""Tests for the seeded player lookup."""

from __future__ import annotations

from bundespredict.agent.players import PlayerInfo, lookup_player


def test_lookup_by_full_name() -> None:
    player = lookup_player("Harry Kane")
    assert player is not None
    assert player.team == "Bayern München"
    assert player.role == "striker"
    assert player.is_penalty_taker is True


def test_lookup_is_case_insensitive() -> None:
    assert lookup_player("harry kane") == lookup_player("Harry Kane")


def test_lookup_by_last_name() -> None:
    player = lookup_player("Kane")
    assert player is not None
    assert player.name == "Harry Kane"


def test_lookup_strips_accents() -> None:
    # "Sesko" (ascii) should resolve "Šeško".
    player = lookup_player("Sesko")
    assert player is not None
    assert player.name == "Benjamin Šeško"


def test_unknown_player_returns_none() -> None:
    assert lookup_player("Nobody McNobodyface") is None


def test_all_seeded_players_validate() -> None:
    # Resolve a known name to force the index to build through PlayerInfo.
    player = lookup_player("Florian Wirtz")
    assert isinstance(player, PlayerInfo)
    assert player.importance in {"high", "medium", "low"}
