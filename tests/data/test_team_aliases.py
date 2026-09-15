"""Tests for canonical team-name resolution."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bundespredict.data.team_aliases import (
    FOOTBALL_DATA_ALIASES,
    OPENLIGADB_ALIASES,
    UnmappedTeamError,
    canonical_team_name,
)
from bundespredict.data.transfermarkt import TRANSFERMARKT_ALIASES

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def test_known_name_maps_to_canonical() -> None:
    assert canonical_team_name("Bayern Munich") == "Bayern Munich"
    assert canonical_team_name("Ein Frankfurt") == "Eintracht Frankfurt"
    assert canonical_team_name("FC Koln") == "1.FC Köln"
    assert canonical_team_name("M'gladbach") == "Borussia Mönchengladbach"


def test_promoted_2026_27_clubs_map_to_canonical() -> None:
    # Spellings taken from football-data's D1_2627.csv; Elversberg crashed the
    # 2026-09-14 scheduled refit.
    assert canonical_team_name("Elversberg") == "SV 07 Elversberg"
    assert canonical_team_name("Paderborn") == "SC Paderborn 07"
    assert canonical_team_name("Schalke 04") == "FC Schalke 04"


def test_every_club_known_to_another_source_has_a_football_data_spelling() -> None:
    """A club added for fixtures or squads will show up in the results CSV too.

    OpenLigaDB and Transfermarkt get updated for a promotion before the first
    football-data CSV exists, so this fails at that point instead of in the
    scheduled refit.
    """
    football_data_canonicals = set(FOOTBALL_DATA_ALIASES.values())
    other_canonicals = set(OPENLIGADB_ALIASES.values()) | set(TRANSFERMARKT_ALIASES.values())
    missing = other_canonicals - football_data_canonicals
    assert not missing, f"no FOOTBALL_DATA_ALIASES entry for: {sorted(missing)}"


def test_surrounding_whitespace_is_ignored() -> None:
    assert canonical_team_name("  Dortmund  ") == "Borussia Dortmund"


def test_unmapped_name_raises_with_helpful_message() -> None:
    with pytest.raises(UnmappedTeamError) as exc:
        canonical_team_name("Real Madrid")
    assert "Real Madrid" in str(exc.value)


def test_empty_name_raises() -> None:
    with pytest.raises(UnmappedTeamError):
        canonical_team_name("")


def test_every_alias_points_at_a_nonempty_canonical_name() -> None:
    for raw, canonical in FOOTBALL_DATA_ALIASES.items():
        assert raw.strip() == raw, f"alias key {raw!r} has stray whitespace"
        assert canonical.strip(), f"alias {raw!r} maps to an empty canonical name"


@pytest.mark.skipif(
    not RAW_DIR.exists() or not any(RAW_DIR.glob("D1_*.csv")),
    reason="no downloaded season CSVs present (data/raw is gitignored)",
)
def test_no_unmapped_team_in_downloaded_seasons() -> None:
    """Local guard: every team string in real CSVs must be in the alias map.

    This is the DoD's 'fail on unmapped name' check against actual data. It is
    skipped in CI (where data/raw is empty) but catches a newly promoted club
    introducing a spelling the moment new seasons are downloaded.
    """
    unmapped: set[str] = set()
    for csv_path in sorted(RAW_DIR.glob("D1_*.csv")):
        with csv_path.open(encoding="latin-1") as fh:
            for row in csv.DictReader(fh):
                for col in ("HomeTeam", "AwayTeam"):
                    name = (row.get(col) or "").strip()
                    if name and name not in FOOTBALL_DATA_ALIASES:
                        unmapped.add(name)
    assert not unmapped, f"unmapped team names in data/raw: {sorted(unmapped)}"
