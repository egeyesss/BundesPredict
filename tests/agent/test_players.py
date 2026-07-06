"""Tests for the player lookup: seeded JSON fallback and the DB-backed path."""

from __future__ import annotations

from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from bundespredict.agent.players import PlayerInfo, lookup_player
from bundespredict.agent.service import PredictionService
from bundespredict.agent.tools import player_to_dict
from bundespredict.data.players import ingest_squads
from bundespredict.data.transfermarkt import LeagueClub, SquadPlayer
from bundespredict.model.dixon_coles import TeamRatings


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


SCRAPED = datetime(2026, 7, 5, 8, 0)


def _service(session: Session) -> PredictionService:
    ratings = TeamRatings(
        teams=("Bayern Munich",),
        attack=np.array([0.0]),
        defense=np.array([0.0]),
        home_adv=0.3,
        rho=-0.1,
        log_likelihood=0.0,
    )
    return PredictionService(ratings, session=session)


def _ingest_bayern(session: Session) -> None:
    squad = [
        SquadPlayer(
            tm_id=1, name="Harry Kane", position="Centre-Forward", market_value_eur=90_000_000
        ),
    ] + [
        SquadPlayer(
            tm_id=10 + i,
            name=f"Depth Player {i}",
            position="Centre-Back",
            market_value_eur=2_000_000,
        )
        for i in range(19)
    ]
    clubs = [
        LeagueClub(
            tm_id=27,
            slug="fc-bayern-munchen",
            name="Bayern Munich",
            season="2526",
            squad_value_eur=900_000_000,
        )
    ]
    ingest_squads(session, clubs, {27: squad}, scraped_at=SCRAPED)


def test_service_lookup_answers_from_db_with_penalty_overlay(session: Session) -> None:
    _ingest_bayern(session)
    player = _service(session).lookup_player("Kane")
    assert player is not None
    assert player.team == "Bayern Munich"  # canonical DB name, not the seed's spelling
    assert player.role == "Centre-Forward"
    assert player.importance == "high"
    assert player.market_value_eur == 90_000_000
    assert player.scraped_at == SCRAPED
    # Penalty duty isn't scraped; it comes from the curated seed overlay.
    assert player.is_penalty_taker is True


def test_service_lookup_db_player_not_in_seed(session: Session) -> None:
    _ingest_bayern(session)
    player = _service(session).lookup_player("Depth Player 3")
    assert player is not None
    assert player.importance == "low"
    assert player.is_penalty_taker is False


def test_service_falls_back_to_seed_when_table_empty(session: Session) -> None:
    player = _service(session).lookup_player("Florian Wirtz")
    assert player is not None
    assert player.scraped_at is None  # the seed carries no snapshot age


def test_tool_result_surfaces_staleness() -> None:
    player = PlayerInfo(
        name="Harry Kane",
        team="Bayern Munich",
        role="Centre-Forward",
        is_penalty_taker=True,
        importance="high",
        market_value_eur=90_000_000,
        scraped_at=SCRAPED,
    )
    payload = player_to_dict(player)
    assert payload["scraped_at"] == "2026-07-05"
    assert payload["market_value_eur"] == 90_000_000
    # The seeded shape omits what it doesn't know rather than sending nulls.
    seed_player = lookup_player("Harry Kane")
    assert seed_player is not None
    seeded = player_to_dict(seed_player)
    assert "scraped_at" not in seeded and "market_value_eur" not in seeded
