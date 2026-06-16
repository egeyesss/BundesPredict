"""Persist and load fitted model parameters.

Training is offline and serving reads persisted parameters, so the engine never
refits inside a request. This module is the bridge between the pure engine's
:class:`~bundespredict.model.dixon_coles.TeamRatings` (keyed by canonical team
name) and the ``model_runs`` / ``team_params`` tables (keyed by ``teams.id``).
Names are resolved to ids on the way in and back to names on the way out, so the
engine and agent never have to know about integer keys.

Like :mod:`bundespredict.data.loader`, this lives in the data layer because it is
the only side that touches the database; the model package stays I/O-free.
"""

from __future__ import annotations

from datetime import date

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.model.dixon_coles import TeamRatings

from .models import ModelRun, Team, TeamParam


def _model_type(rho: float) -> str:
    """A run with rho pinned at 0 was fit as plain independent Poisson."""
    return "independent_poisson" if rho == 0.0 else "dixon_coles"


def save_ratings(
    session: Session,
    ratings: TeamRatings,
    *,
    xi: float,
    n_matches: int,
    as_of_date: date | None = None,
    version: str | None = None,
    notes: str | None = None,
) -> int:
    """Persist ``ratings`` as one ``model_runs`` row plus its ``team_params``.

    ``xi`` (the decay rate the fit used) and ``n_matches`` aren't carried on
    :class:`TeamRatings`, so the caller supplies them. Returns the new run id.
    Commits so the run is durable for later serving/backtest reads.
    """
    name_to_id: dict[str, int] = dict(
        session.execute(select(Team.name, Team.id).where(Team.name.in_(ratings.teams)))
        .tuples()
        .all()
    )
    missing = set(ratings.teams) - name_to_id.keys()
    if missing:
        raise ValueError(f"no teams row for: {sorted(missing)}")

    run = ModelRun(
        model_type=_model_type(ratings.rho),
        as_of_date=as_of_date,
        xi=xi,
        rho=ratings.rho,
        home_adv=ratings.home_adv,
        log_likelihood=ratings.log_likelihood,
        n_matches=n_matches,
        version=version,
        notes=notes,
        team_params=[
            TeamParam(
                team_id=name_to_id[name],
                attack=float(ratings.attack[i]),
                defense=float(ratings.defense[i]),
            )
            for i, name in enumerate(ratings.teams)
        ],
    )
    session.add(run)
    session.commit()
    return run.id


def load_ratings(session: Session, model_run_id: int) -> TeamRatings:
    """Reconstruct a :class:`TeamRatings` from a persisted run.

    Teams are ordered by canonical name (matching the loader's convention), so a
    round-tripped fit indexes identically to a freshly loaded one.
    """
    run = session.get(ModelRun, model_run_id)
    if run is None:
        raise ValueError(f"no model_run with id {model_run_id}")

    rows = session.execute(
        select(Team.name, TeamParam.attack, TeamParam.defense)
        .join(Team, Team.id == TeamParam.team_id)
        .where(TeamParam.model_run_id == model_run_id)
        .order_by(Team.name)
    ).all()
    if not rows:
        raise ValueError(f"model_run {model_run_id} has no team_params")

    teams = tuple(r[0] for r in rows)
    attack = np.array([r[1] for r in rows], dtype=np.float64)
    defense = np.array([r[2] for r in rows], dtype=np.float64)
    return TeamRatings(
        teams=teams,
        attack=attack,
        defense=defense,
        home_adv=run.home_adv,
        rho=run.rho,
        log_likelihood=run.log_likelihood,
    )


def latest_run_id(session: Session, *, as_of_date: date | None = None) -> int | None:
    """Id of the most recently trained run, optionally for a specific cutoff.

    Serving wants the freshest parameters; the backtest wants the run it wrote
    for a given gameweek. ``None`` when nothing has been persisted yet.
    """
    stmt = select(ModelRun.id).order_by(ModelRun.trained_at.desc(), ModelRun.id.desc())
    if as_of_date is not None:
        stmt = stmt.where(ModelRun.as_of_date == as_of_date)
    return session.execute(stmt.limit(1)).scalar_one_or_none()
