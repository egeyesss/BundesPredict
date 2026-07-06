"""Transfermarkt parser tests against committed page snapshots.

The fixtures are real pages (gzipped to keep the repo lean): two squad pages
and two league pages, one current and one historical each. If Transfermarkt
changes its markup these break loudly — that's the point; re-record and adjust.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from bundespredict.data.team_aliases import UnmappedTeamError
from bundespredict.data.transfermarkt import (
    canonical_club_name,
    parse_league_page,
    parse_market_value,
    parse_squad_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _page(name: str) -> str:
    return gzip.open(FIXTURES / name, "rt", encoding="utf-8").read()


def test_parse_market_value() -> None:
    assert parse_market_value("€18.00m") == 18_000_000
    assert parse_market_value("€500k") == 500_000
    assert parse_market_value("€1.06bn") == 1_060_000_000
    assert parse_market_value("-") is None
    with pytest.raises(ValueError, match="unparseable"):
        parse_market_value("18 million")


def test_parse_league_page_current() -> None:
    clubs = parse_league_page(_page("tm_league_2025.html.gz"), 2025)
    assert len(clubs) == 18
    by_name = {c.name: c for c in clubs}
    bayern = by_name["Bayern Munich"]
    assert bayern.tm_id == 27
    assert bayern.slug == "fc-bayern-munchen"
    assert bayern.season == "2526"
    assert bayern.squad_value_eur is not None and bayern.squad_value_eur > 500_000_000
    # Every club name must resolve canonically — the fail-loud guard in one sweep.
    for club in clubs:
        canonical_club_name(club.name)


def test_parse_league_page_historical_values_are_era_correct() -> None:
    clubs = parse_league_page(_page("tm_league_2019.html.gz"), 2019)
    by_name = {c.name: c for c in clubs}
    assert by_name["SC Paderborn 07"].season == "1920"
    # Schalke's 2019/20 squad was worth ~€220m; today's is nowhere near.
    # If this drifts to a small number, TM started serving current values
    # on historical pages and the shrinkage prior loses its backtest story.
    schalke = by_name["FC Schalke 04"].squad_value_eur
    assert schalke is not None and schalke > 150_000_000


def test_parse_squad_page_full_roster() -> None:
    players = parse_squad_page(_page("tm_squad_bayern.html.gz"))
    assert len(players) == 40  # full contracted squad, injured players included
    by_name = {p.name: p for p in players}
    # An injured player (icon inside the anchor) must still parse.
    assert "Serge Gnabry" in by_name
    # And the captain (captain icon inside the anchor).
    neuer = by_name["Manuel Neuer"]
    assert neuer.tm_id == 17259
    assert neuer.position == "Goalkeeper"
    assert neuer.market_value_eur == 4_000_000
    assert len({p.tm_id for p in players}) == len(players)  # ids unique


def test_parse_squad_page_positions_and_missing_values() -> None:
    players = parse_squad_page(_page("tm_squad_heidenheim.html.gz"))
    assert len(players) >= 25
    assert all(p.position for p in players)
    # Market value may legitimately be missing ("-"), but never zero.
    assert all(v is None or v > 0 for v in (p.market_value_eur for p in players))


def test_unmapped_club_fails_loudly() -> None:
    with pytest.raises(UnmappedTeamError, match="1860 Munich"):
        canonical_club_name("1860 Munich")


def test_squad_parser_rejects_markup_drift() -> None:
    with pytest.raises(ValueError, match="markup"):
        parse_squad_page("<html><body>redesigned page</body></html>")
    with pytest.raises(ValueError, match="markup"):
        parse_league_page("<html><body>redesigned page</body></html>", 2025)
