"""Crest identity (code and short name) for each canonical club name.

Codes and short names are the keys the web crest set uses, so they have to stay in step with it.
A club missing from this map gets no code, and fixtures involving it are left off the matchday.
Migration 0004 keeps its own frozen copy for databases that already had teams when it ran.
"""

from __future__ import annotations

from football.models import Team

CLUB_IDENTITIES: dict[str, tuple[str, str]] = {
    "Bayern Munich": ("FCB", "Bayern"),
    "Borussia Dortmund": ("BVB", "Dortmund"),
    "Bayer 04 Leverkusen": ("B04", "Leverkusen"),
    "RB Leipzig": ("RBL", "Leipzig"),
    "Eintracht Frankfurt": ("SGE", "Frankfurt"),
    "VfB Stuttgart": ("VFB", "Stuttgart"),
    "SC Freiburg": ("SCF", "Freiburg"),
    "Borussia Mönchengladbach": ("BMG", "Gladbach"),
    "1.FSV Mainz 05": ("M05", "Mainz"),
    "TSG 1899 Hoffenheim": ("TSG", "Hoffenheim"),
    "SV Werder Bremen": ("SVW", "Bremen"),
    "FC Augsburg": ("FCA", "Augsburg"),
    "1.FC Union Berlin": ("FCU", "Union Berlin"),
    "1.FC Köln": ("KOE", "Köln"),
    "Hamburger SV": ("HSV", "Hamburg"),
    "FC Schalke 04": ("S04", "Schalke"),
    "SC Paderborn 07": ("SCP", "Paderborn"),
    "SV 07 Elversberg": ("SVE", "Elversberg"),
}


def new_team(name: str) -> Team:
    """An unsaved team row for a canonical name, with its crest identity when one is known."""
    code, short_name = CLUB_IDENTITIES.get(name, (None, None))
    return Team(name=name, code=code, short_name=short_name)
