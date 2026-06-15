"""Canonical Bundesliga team names and source-name aliasing.

Canonical names follow Transfermarkt's club naming, since Transfermarkt is the
source we scrape later for squads/market value (see vault decisions.md). Each
data source spells clubs its own way; football-data.co.uk uses short strings
like ``Ein Frankfurt`` or ``FC Koln``. ``FOOTBALL_DATA_ALIASES`` maps every
football-data string we've seen to the canonical name.

The canonical strings here are best-effort Transfermarkt-style names. They get
reconciled exactly against real Transfermarkt output (joined on a numeric club
id) when the scrape lands in a later phase; until then nothing downstream
depends on the precise string, only on the mapping being total.
"""

from __future__ import annotations


class UnmappedTeamError(KeyError):
    """Raised when a source team name has no canonical mapping.

    Subclasses ``KeyError`` so it reads naturally, but carries a clear message
    so an unmapped club (e.g. a newly promoted side) fails loudly at ingest
    instead of silently creating a duplicate team.
    """


# football-data.co.uk name -> canonical (Transfermarkt-style) name.
# Covers every club seen in Bundesliga seasons 2019/20 through 2025/26.
FOOTBALL_DATA_ALIASES: dict[str, str] = {
    "Augsburg": "FC Augsburg",
    "Bayern Munich": "Bayern Munich",
    "Bielefeld": "Arminia Bielefeld",
    "Bochum": "VfL Bochum",
    "Darmstadt": "SV Darmstadt 98",
    "Dortmund": "Borussia Dortmund",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "FC Koln": "1.FC Köln",
    "Fortuna Dusseldorf": "Fortuna Düsseldorf",
    "Freiburg": "SC Freiburg",
    "Greuther Furth": "SpVgg Greuther Fürth",
    "Hamburg": "Hamburger SV",
    "Heidenheim": "1.FC Heidenheim 1846",
    "Hertha": "Hertha BSC",
    "Hoffenheim": "TSG 1899 Hoffenheim",
    "Holstein Kiel": "Holstein Kiel",
    "Leverkusen": "Bayer 04 Leverkusen",
    "M'gladbach": "Borussia Mönchengladbach",
    "Mainz": "1.FSV Mainz 05",
    "Paderborn": "SC Paderborn 07",
    "RB Leipzig": "RB Leipzig",
    "Schalke 04": "FC Schalke 04",
    "St Pauli": "FC St. Pauli",
    "Stuttgart": "VfB Stuttgart",
    "Union Berlin": "1.FC Union Berlin",
    "Werder Bremen": "SV Werder Bremen",
    "Wolfsburg": "VfL Wolfsburg",
}


def canonical_team_name(raw: str, *, source_aliases: dict[str, str] = FOOTBALL_DATA_ALIASES) -> str:
    """Resolve a raw source team name to its canonical name.

    Raises:
        UnmappedTeamError: if ``raw`` (after trimming) is not in the alias map.
    """
    key = raw.strip()
    try:
        return source_aliases[key]
    except KeyError as exc:
        raise UnmappedTeamError(
            f"no canonical mapping for team name {raw!r}; add it to "
            "FOOTBALL_DATA_ALIASES in team_aliases.py"
        ) from exc
