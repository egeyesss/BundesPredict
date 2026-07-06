"""Transfermarkt page parsing: league tables (clubs + squad values) and squads.

Transfermarkt is the squad/market-value source the canonical team names were
chosen to match from day one. This module is the *pure* half of the scrape:
HTML text in, typed rows out — no network, no DB — so the parsers are testable
against committed page snapshots and the scraper script stays a thin
fetch-and-cache orchestrator.

Two page types matter:

* The **league page** for a season (``.../bundesliga/startseite/wettbewerb/L1``)
  lists that season's 18 clubs with Transfermarkt's numeric club id, the URL
  slug, and the squad's total market value. Historical seasons show
  era-correct values (verified: the 2019 page prices Schalke at €221m), which
  is what makes the value-implied shrinkage prior backtestable.
* The **squad page** for a club (``.../<slug>/kader/verein/<id>``) lists every
  contracted player with Transfermarkt's numeric player id, position, and
  market value.

Joins to our ``teams`` table go through the numeric club id once it's stored;
the name alias map below exists to *establish* that link (and to fail loudly
if Transfermarkt renames a club or a new one appears), never for row joins.

Parsing is regex-based on purpose: the pages are server-rendered with stable
class names, the two patterns we anchor on (``inline-table`` for players,
``startseite/verein`` hrefs for clubs) have survived years of reskins, and a
full HTML parser would add a dependency without removing the need to re-record
fixtures when the markup truly changes. The sanity checks in each parser are
the tripwire for that day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .team_aliases import canonical_team_name

# Transfermarkt club name -> canonical name. Canonical names were chosen to
# match Transfermarkt, so today this is the identity map — but it stays an
# explicit allowlist so an unexpected spelling (a renamed club, a promotion we
# haven't seen, a markup change that garbles names) raises UnmappedTeamError
# at ingest instead of silently creating a duplicate team.
TRANSFERMARKT_ALIASES: dict[str, str] = {
    "1.FC Heidenheim 1846": "1.FC Heidenheim 1846",
    "1.FC Köln": "1.FC Köln",
    "1.FC Union Berlin": "1.FC Union Berlin",
    "1.FSV Mainz 05": "1.FSV Mainz 05",
    "Arminia Bielefeld": "Arminia Bielefeld",
    "Bayer 04 Leverkusen": "Bayer 04 Leverkusen",
    "Bayern Munich": "Bayern Munich",
    "Borussia Dortmund": "Borussia Dortmund",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "FC Augsburg": "FC Augsburg",
    "FC Schalke 04": "FC Schalke 04",
    "FC St. Pauli": "FC St. Pauli",
    "Fortuna Düsseldorf": "Fortuna Düsseldorf",
    "Hamburger SV": "Hamburger SV",
    "Hertha BSC": "Hertha BSC",
    "Holstein Kiel": "Holstein Kiel",
    "RB Leipzig": "RB Leipzig",
    "SC Freiburg": "SC Freiburg",
    "SC Paderborn 07": "SC Paderborn 07",
    "SpVgg Greuther Fürth": "SpVgg Greuther Fürth",
    "SV 07 Elversberg": "SV 07 Elversberg",
    "SV Darmstadt 98": "SV Darmstadt 98",
    "SV Werder Bremen": "SV Werder Bremen",
    "TSG 1899 Hoffenheim": "TSG 1899 Hoffenheim",
    "VfB Stuttgart": "VfB Stuttgart",
    "VfL Bochum": "VfL Bochum",
    "VfL Wolfsburg": "VfL Wolfsburg",
}


@dataclass(frozen=True)
class LeagueClub:
    """One club row from a season's league page, name still source-spelled."""

    tm_id: int
    slug: str  # URL path segment, needed to build the squad-page URL
    name: str
    season: str  # e.g. "1920"
    squad_value_eur: int | None


@dataclass(frozen=True)
class SquadPlayer:
    """One player row from a club's squad page."""

    tm_id: int
    name: str
    position: str
    market_value_eur: int | None


_VALUE = re.compile(r"^€([\d.]+)(bn|m|k)?$")
_MULTIPLIER = {"bn": 1_000_000_000, "m": 1_000_000, "k": 1_000, None: 1}

_CLUB_LINK = re.compile(
    r'href="/([^"/]+)/startseite/verein/(\d+)/saison_id/(\d+)"[^>]*>([^<]+)</a>'
)
_ROW_VALUE = re.compile(r">(€[\d.,]+(?:bn|m|k)?|-)</a>")

_INLINE_TABLE = re.compile(r'<table class="inline-table">(.*?)</table>', re.S)
# Name is the text between the profile anchor and the first nested tag —
# injured/captain players carry an icon <span> inside the anchor after the name.
_PLAYER_LINK = re.compile(r'href="/[^"/]+/profil/spieler/(\d+)"[^>]*>\s*([^<]+?)\s*(?:<|</a>)')
_PLAYER_POSITION = re.compile(r"<tr>\s*<td>\s*([^<]+?)\s*</td>\s*</tr>\s*$", re.S)
_PLAYER_VALUE = re.compile(r'class="rechts hauptlink">\s*(?:<a[^>]*>)?\s*(€[\d.,]+(?:bn|m|k)?|-)')


def parse_market_value(text: str) -> int | None:
    """``"€18.00m"`` -> 18_000_000; ``"-"`` (no valuation) -> ``None``."""
    cleaned = text.strip().replace(",", "")
    if cleaned in ("-", ""):
        return None
    match = _VALUE.match(cleaned)
    if match is None:
        raise ValueError(f"unparseable market value: {text!r}")
    return int(round(float(match.group(1)) * _MULTIPLIER[match.group(2)]))


def _season_code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def parse_league_page(html: str, start_year: int) -> list[LeagueClub]:
    """Extract the 18 clubs (id, slug, name, squad value) from a league page.

    The page contains each club link many times (table, matchday widgets); we
    keep the first occurrence per club id, which sits in the clubs table where
    the same row also carries the squad's total market value. Exactly 18 clubs
    are required — anything else means Transfermarkt changed the markup and the
    scrape must fail loudly, not half-ingest.
    """
    clubs: dict[int, LeagueClub] = {}
    for link in _CLUB_LINK.finditer(html):
        tm_id = int(link.group(2))
        if tm_id in clubs:
            continue
        # The squad value sits in the same table row; search a bounded window
        # after the link so a later widget's numbers can't be picked up.
        window = html[link.end() : link.end() + 2_000]
        value_match = _ROW_VALUE.search(window)
        clubs[tm_id] = LeagueClub(
            tm_id=tm_id,
            slug=link.group(1),
            name=link.group(4).strip(),
            season=_season_code(start_year),
            squad_value_eur=parse_market_value(value_match.group(1)) if value_match else None,
        )
    if len(clubs) != 18:
        raise ValueError(
            f"league page for {start_year} parsed {len(clubs)} clubs, expected 18 — "
            "Transfermarkt markup may have changed"
        )
    return list(clubs.values())


def parse_squad_page(html: str) -> list[SquadPlayer]:
    """Extract every player (id, name, position, market value) from a squad page.

    Each player row nests an ``inline-table`` holding the profile link and the
    position; the market-value cell follows the inline table in the outer row.
    A real squad has 20+ contracted players, so fewer than 15 parsed rows is
    treated as markup drift and raised, same policy as the league parser.
    """
    players: list[SquadPlayer] = []
    seen: set[int] = set()
    for block in _INLINE_TABLE.finditer(html):
        player = _PLAYER_LINK.search(block.group(1))
        if player is None:
            continue
        tm_id = int(player.group(1))
        if tm_id in seen:  # pragma: no cover - defensive against repeated widgets
            continue
        position = _PLAYER_POSITION.search(block.group(1))
        if position is None:
            raise ValueError(f"no position found for player {player.group(2)!r}")
        value = _PLAYER_VALUE.search(html, block.end())
        players.append(
            SquadPlayer(
                tm_id=tm_id,
                name=player.group(2).strip(),
                position=position.group(1).strip(),
                market_value_eur=parse_market_value(value.group(1)) if value else None,
            )
        )
        seen.add(tm_id)
    if len(players) < 15:
        raise ValueError(
            f"squad page parsed only {len(players)} players — Transfermarkt markup may have changed"
        )
    return players


def canonical_club_name(tm_name: str) -> str:
    """Resolve a Transfermarkt club name to canonical, failing loudly if unmapped."""
    return canonical_team_name(tm_name, source_aliases=TRANSFERMARKT_ALIASES)
