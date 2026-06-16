"""SQLAlchemy ORM models for the data layer.

``teams``, ``team_aliases``, and ``matches`` back the data layer; ``model_runs``
and ``team_params`` persist fitted model state so serving and backtests read
versioned parameters instead of refitting live. ``predictions`` is still
deferred to the agent phase that defines its columns.

Naming is canonical-first: a ``Team`` row holds one canonical name; every raw
source spelling (football-data now, Transfermarkt/FBref later) lives in
``team_aliases``. Cross-source joins go through these keys, never through name
strings.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func
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
    # The plain columns are the early/posted price; the ``*c_*`` columns are the
    # closing price (football-data's "C" suffix). CLV needs both: we bet at the
    # early line and measure whether the closing line moved toward us.
    b365_home: Mapped[float | None]
    b365_draw: Mapped[float | None]
    b365_away: Mapped[float | None]
    avg_home: Mapped[float | None]
    avg_draw: Mapped[float | None]
    avg_away: Mapped[float | None]
    b365c_home: Mapped[float | None]
    b365c_draw: Mapped[float | None]
    b365c_away: Mapped[float | None]
    avgc_home: Mapped[float | None]
    avgc_draw: Mapped[float | None]
    avgc_away: Mapped[float | None]


class ModelRun(Base):
    """One fitted model — the run-level state shared across all its teams.

    A run is the unit of versioning: training is offline and serving reads the
    persisted parameters, so the engine never refits inside a request. The
    walk-forward backtest writes one run per cutoff, with ``as_of_date`` set to
    that cutoff, which makes every gameweek's prediction auditable back to the
    exact parameters that produced it.
    """

    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(server_default=func.now())
    model_type: Mapped[str]  # "dixon_coles" | "independent_poisson"
    # The walk-forward cutoff this run was fit for (matches strictly before it).
    # None for a full-history fit not tied to a single prediction date.
    as_of_date: Mapped[date | None] = mapped_column(index=True)
    xi: Mapped[float]  # time-decay rate the fit used (0 = no decay)
    rho: Mapped[float]  # Dixon-Coles correction (0 = independent Poisson)
    home_adv: Mapped[float]  # gamma, the log-space home advantage
    log_likelihood: Mapped[float]
    n_matches: Mapped[int]  # weighted match count the fit saw
    version: Mapped[str | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)

    team_params: Mapped[list[TeamParam]] = relationship(
        back_populates="model_run", cascade="all, delete-orphan"
    )


class TeamParam(Base):
    """One team's attack/defense strengths within a model run (log space)."""

    __tablename__ = "team_params"
    __table_args__ = (UniqueConstraint("model_run_id", "team_id", name="uq_team_param_run_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # A team_param is wholly owned by its run; deleting the run deletes its params
    # (DB-level cascade, so bulk deletes stay consistent too).
    model_run_id: Mapped[int] = mapped_column(
        ForeignKey("model_runs.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    attack: Mapped[float]
    defense: Mapped[float]

    model_run: Mapped[ModelRun] = relationship(back_populates="team_params")
