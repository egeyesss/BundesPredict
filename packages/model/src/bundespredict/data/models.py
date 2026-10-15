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
from typing import Any

from sqlalchemy import JSON, BigInteger, ForeignKey, UniqueConstraint, func
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

    # Per-match expected goals from Understat (nullable: older seasons or the
    # unplayed current-season rows may lack coverage). These are *final-match* xG
    # and must never feed a prediction directly — the model only ever consumes a
    # rolling average over matches strictly before kickoff (see data/loader.py).
    home_xg: Mapped[float | None]
    away_xg: Mapped[float | None]

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


class Fixture(Base):
    """One scheduled (not yet played) match from the fixtures source.

    Kept separate from ``matches`` on purpose: a ``Match`` row is a completed
    result and its columns are non-null by design, while a fixture is only a
    kickoff time and a pairing. The fixtures ingest replaces a whole season's
    rows atomically, so this table always mirrors the source's current schedule
    (kickoffs move when matchdays get rescheduled).
    """

    __tablename__ = "fixtures"
    __table_args__ = (
        # Matchday is part of the key: sources have shipped the same pairing on
        # two matchdays (a mis-entered derby return leg), and the mirror must be
        # able to represent whatever the source says.
        UniqueConstraint(
            "season", "matchday", "home_id", "away_id", name="uq_fixture_season_md_home_away"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(index=True)  # e.g. "2627"
    matchday: Mapped[int]
    kickoff_utc: Mapped[datetime] = mapped_column(index=True)  # naive UTC
    home_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)


class Player(Base):
    """One squad member from the Transfermarkt scrape.

    The table mirrors the source's current squads (ingest replaces a team's
    roster wholesale, players transfer away mid-season), so rows carry
    ``scraped_at`` and the lookup surfaces it — a stale snapshot should be
    visible to the agent, not silently trusted. ``tm_id`` is Transfermarkt's
    stable numeric player id and the only cross-scrape join key; names are for
    matching user queries, never for joins.
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    tm_id: Mapped[int] = mapped_column(unique=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    position: Mapped[str]  # Transfermarkt's position label, e.g. "Centre-Forward"
    # BigInteger: squad totals stay under int32, but this column also stores
    # star-player valuations that get close enough to be uncomfortable.
    market_value_eur: Mapped[int | None] = mapped_column(BigInteger)
    scraped_at: Mapped[datetime]

    team: Mapped[Team] = relationship()


class SquadValue(Base):
    """A club's total squad market value for one season (from the league page).

    Season pages carry era-correct values, which is what makes this usable as
    a backtest input: the value-implied shrinkage target for a promoted team in
    2019 is built from 2019 values, not today's.
    """

    __tablename__ = "squad_values"
    __table_args__ = (UniqueConstraint("season", "team_id", name="uq_squad_value_season_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(index=True)  # e.g. "1920"
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    value_eur: Mapped[int] = mapped_column(BigInteger)
    scraped_at: Mapped[datetime]

    team: Mapped[Team] = relationship()


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
    # Global coefficient on the pre-match rolling-xG offset in log-lambda. 0 for
    # a goals-only fit (the model then reduces exactly to the pre-xG engine), so
    # the server_default keeps every existing run behaving as before.
    xg_coef: Mapped[float] = mapped_column(default=0.0, server_default="0")
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


class Prediction(Base):
    """One agent answer, persisted so every response is auditable.

    The served distribution is what the user saw; the ``base_*`` columns keep the
    pre-adjustment baseline so the UI can show baseline-vs-adjusted side by side
    and a reviewer can see exactly what the context changed. ``adjustments_json``
    is the list of applied :class:`~bundespredict.agent.adjustments.Adjustment`s
    (with their effective, clamped magnitudes) — the "show your work" record that
    makes the agent layer transparent rather than a black box.

    ``model_run_id`` ties the prediction back to the exact fitted parameters that
    produced it, so an answer stays reproducible even after the model is refit.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id"), index=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    match_date: Mapped[date | None]

    # The natural-language request that produced this prediction (audit context).
    query: Mapped[str | None]

    # Served (post-adjustment) 1X2 + expected goals — what the user actually saw.
    p_home: Mapped[float]
    p_draw: Mapped[float]
    p_away: Mapped[float]
    exp_home_goals: Mapped[float]
    exp_away_goals: Mapped[float]

    # Pre-adjustment baseline 1X2, kept for the side-by-side comparison.
    base_p_home: Mapped[float]
    base_p_draw: Mapped[float]
    base_p_away: Mapped[float]

    # The applied adjustments (factor/team/target/magnitude/confidence/rationale)
    # and the agent's natural-language explanation.
    adjustments_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    explanation: Mapped[str | None]
