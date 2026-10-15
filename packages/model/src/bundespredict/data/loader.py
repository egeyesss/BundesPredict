"""DB -> arrays bridge for the pure model engine.

The engine in ``model/`` never touches the database. This loader is the seam:
it pulls match rows into plain integer-indexed numpy arrays and hands them over
as :class:`~bundespredict.model.dixon_coles.MatchData`. Team identifiers are the
canonical team names, contiguously indexed over whatever teams appear in the
queried slice.

Leakage discipline is built in from day one: ``as_of_date`` filters to matches
played **strictly before** it, so a fit for a fixture on date D only ever sees
results that were known before kickoff. Walk-forward backtesting (Phase 3) just
calls this repeatedly with a moving ``as_of_date``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.model.dixon_coles import MatchData

from .dated_matches import DatedMatches, MatchRecord, XgGaps
from .models import Match, Team

__all__ = ["DatedMatches", "XgGaps", "load_dated_matches", "load_match_data"]


def load_dated_matches(
    session: Session,
    *,
    as_of_date: date | None = None,
    seasons: Sequence[str] | None = None,
) -> DatedMatches:
    """Pull matches into arrays, optionally filtered for leakage and by season.

    Only matches played strictly before ``as_of_date`` are returned (when given),
    so nothing from on/after the prediction date can leak into a fit. Teams are
    indexed over exactly the clubs that appear in the returned slice.
    """
    stmt = (
        select(
            Match.home_id,
            Match.away_id,
            Match.home_goals,
            Match.away_goals,
            Match.date,
            Match.home_xg,
            Match.away_xg,
        )
        .join(Team, Team.id == Match.home_id)
        .order_by(Match.date, Match.id)
    )
    if as_of_date is not None:
        stmt = stmt.where(Match.date < as_of_date)
    if seasons is not None:
        stmt = stmt.where(Match.season.in_(seasons))

    rows = session.execute(stmt).all()
    if not rows:
        raise ValueError("no matches matched the given filters")

    team_ids = {row[0] for row in rows} | {row[1] for row in rows}
    id_to_name: dict[int, str] = dict(
        session.execute(select(Team.id, Team.name).where(Team.id.in_(team_ids))).tuples().all()
    )
    return DatedMatches.from_records(
        [
            MatchRecord(
                home=id_to_name[r[0]],
                away=id_to_name[r[1]],
                home_goals=r[2],
                away_goals=r[3],
                played_on=r[4],
                home_xg=r[5],
                away_xg=r[6],
            )
            for r in rows
        ]
    )


def load_match_data(
    session: Session,
    *,
    as_of_date: date | None = None,
    seasons: Sequence[str] | None = None,
    xi: float = 0.0,
    use_xg: bool = False,
) -> MatchData:
    """One-shot convenience: load matches and apply time decay in a single call."""
    dated = load_dated_matches(session, as_of_date=as_of_date, seasons=seasons)
    return dated.to_match_data(xi=xi, reference=as_of_date, use_xg=use_xg)
