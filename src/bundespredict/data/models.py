"""SQLAlchemy ORM models for the data layer.

Phase 1 defines only the tables this phase populates: ``teams``,
``team_aliases``, and ``matches``. ``model_runs`` / ``team_params`` /
``predictions`` are added in the phases that define their columns.

Naming is canonical-first: a ``Team`` row holds one canonical name; every raw
source spelling (football-data now, Transfermarkt/FBref later) lives in
``team_aliases``. Cross-source joins go through these keys, never through name
strings.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)  # canonical (Transfermarkt-style)
    # Transfermarkt numeric club id; filled when the scrape lands (stable join key).
    tm_id: Mapped[int | None] = mapped_column(unique=True, default=None)

    aliases: Mapped[list[TeamAlias]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamAlias(Base):
    """A raw source spelling that resolves to a canonical team."""

    __tablename__ = "team_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(unique=True)  # raw source string
    source: Mapped[str]  # e.g. "football-data"
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))

    team: Mapped[Team] = relationship(back_populates="aliases")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        # One fixture per (season, home, away) in a round-robin league; this is
        # the natural key that makes re-ingestion idempotent.
        UniqueConstraint("season", "home_id", "away_id", name="uq_match_season_home_away"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(index=True)  # e.g. "2324"
    date: Mapped[date] = mapped_column(index=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)

    # Full-time result — never null (unplayed fixtures are dropped at parse time).
    home_goals: Mapped[int]
    away_goals: Mapped[int]
    ftr: Mapped[str]  # 'H' | 'D' | 'A'

    # Half-time result.
    ht_home_goals: Mapped[int | None]
    ht_away_goals: Mapped[int | None]
    htr: Mapped[str | None]

    # Match stats.
    home_shots: Mapped[int | None]
    away_shots: Mapped[int | None]
    home_sot: Mapped[int | None]
    away_sot: Mapped[int | None]
    home_fouls: Mapped[int | None]
    away_fouls: Mapped[int | None]
    home_corners: Mapped[int | None]
    away_corners: Mapped[int | None]
    home_yellows: Mapped[int | None]
    away_yellows: Mapped[int | None]
    home_reds: Mapped[int | None]
    away_reds: Mapped[int | None]

    # Bookmaker odds: Bet365 1X2 (benchmark) + market average (de-vig baseline).
    b365_home: Mapped[float | None]
    b365_draw: Mapped[float | None]
    b365_away: Mapped[float | None]
    avg_home: Mapped[float | None]
    avg_draw: Mapped[float | None]
    avg_away: Mapped[float | None]
