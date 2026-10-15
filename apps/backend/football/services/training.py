"""Training data in, `ModelRun` out. Training runs offline; serving only reads the newest run.

Every read that feeds a fit takes an explicit `as_of` and returns matches played strictly
before it, so a run labelled with that date has never seen a later result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from django.db import close_old_connections, connection, transaction

from bundespredict.data.dated_matches import DatedMatches, MatchRecord
from bundespredict.data.fitting import fit_shrunk_ratings
from bundespredict.data.seasons import results_season_start, season_code
from bundespredict.model.dixon_coles import TeamRatings
from football.models import Match, ModelRun, SquadValue, Team, TeamParam

logger = logging.getLogger(__name__)

SERVE_VERSION = "serve"
DEFAULT_XI = 0.004
SAME_RUN_TOLERANCE = 1e-9


def refresh_connection() -> None:
    """Drop the database connection if the server closed it while a long fit was running.

    Neon suspends idle compute and management commands get no request-start health check.
    Skipped inside a transaction, where closing would throw the work away.
    """
    if not connection.in_atomic_block:
        close_old_connections()


def load_dated_matches(*, as_of: date | None) -> DatedMatches:
    """Played matches strictly before `as_of` as engine-ready arrays, ordered by date then id.

    `as_of=None` means no cutoff and is only for choosing hyperparameters on the whole history.
    """
    matches = Match.objects.order_by("date", "id")
    if as_of is not None:
        matches = matches.filter(date__lt=as_of)
    return DatedMatches.from_records(
        [
            MatchRecord(
                home=home,
                away=away,
                home_goals=home_goals,
                away_goals=away_goals,
                played_on=played_on,
                home_xg=home_xg,
                away_xg=away_xg,
            )
            for home, away, home_goals, away_goals, played_on, home_xg, away_xg in (
                matches.values_list(
                    "home__name",
                    "away__name",
                    "home_goals",
                    "away_goals",
                    "date",
                    "home_xg",
                    "away_xg",
                )
            )
        ]
    )


def squad_values_for_season(code: str) -> dict[str, int]:
    return dict(SquadValue.objects.filter(season=code).values_list("team__name", "value_eur"))


def model_type_for(rho: float) -> str:
    """A run with rho pinned at 0 was fit as plain independent Poisson."""
    return "independent_poisson" if rho == 0.0 else "dixon_coles"


def save_model_run(
    ratings: TeamRatings,
    *,
    xi: float,
    n_matches: int,
    as_of_date: date | None,
    version: str,
    notes: str,
) -> ModelRun:
    """Persist `ratings` as one `ModelRun` with its `TeamParam` rows, atomically."""
    team_ids = dict(Team.objects.filter(name__in=ratings.teams).values_list("name", "id"))
    missing = set(ratings.teams) - team_ids.keys()
    if missing:
        raise ValueError(f"no teams row for: {sorted(missing)}")
    with transaction.atomic():
        run = ModelRun.objects.create(
            model_type=model_type_for(ratings.rho),
            as_of_date=as_of_date,
            xi=xi,
            rho=ratings.rho,
            home_adv=ratings.home_adv,
            xg_coef=ratings.xg_coef,
            log_likelihood=ratings.log_likelihood,
            n_matches=n_matches,
            version=version,
            notes=notes,
        )
        TeamParam.objects.bulk_create(
            [
                TeamParam(
                    model_run=run,
                    team_id=team_ids[name],
                    attack=float(ratings.attack[i]),
                    defense=float(ratings.defense[i]),
                )
                for i, name in enumerate(ratings.teams)
            ]
        )
    return run


def run_matches_ratings(run: ModelRun, ratings: TeamRatings, *, xi: float) -> bool:
    """Whether `run` already stores exactly these ratings (within float noise)."""
    scalars = (
        (run.xi, xi),
        (run.rho, ratings.rho),
        (run.home_adv, ratings.home_adv),
        (run.xg_coef, ratings.xg_coef),
        (run.log_likelihood, ratings.log_likelihood),
    )
    if any(abs(stored - fresh) > SAME_RUN_TOLERANCE for stored, fresh in scalars):
        return False
    stored_params = {
        name: (attack, defense)
        for name, attack, defense in TeamParam.objects.filter(model_run=run).values_list(
            "team__name", "attack", "defense"
        )
    }
    if stored_params.keys() != set(ratings.teams):
        return False
    return all(
        abs(stored_params[name][0] - ratings.attack[i]) <= SAME_RUN_TOLERANCE
        and abs(stored_params[name][1] - ratings.defense[i]) <= SAME_RUN_TOLERANCE
        for i, name in enumerate(ratings.teams)
    )


@dataclass(frozen=True)
class RefitOutcome:
    run: ModelRun
    created: bool
    n_matches: int
    ratings: TeamRatings
    xi: float
    squad_values_used: int


def refit_serving_model(
    *, as_of: date, xi: float | None = None, select_xi_on_history: bool = False, force: bool = False
) -> RefitOutcome:
    """Fit on every result before `as_of` and store it as the newest serving run.

    A run already stored for the same cutoff, data size and parameters is reused instead of
    duplicated, so re-running without new results changes nothing. `force` always writes.
    """
    dated = load_dated_matches(as_of=as_of)
    if xi is None:
        if select_xi_on_history:
            from bundespredict.model.time_decay import select_xi

            selected = select_xi(
                dated.teams,
                dated.home_idx,
                dated.away_idx,
                dated.home_goals,
                dated.away_goals,
                dated.day_ordinal,
            )
            xi = selected.xi
            logger.info("selected xi=%.4f walk-forward", xi)
        else:
            xi = DEFAULT_XI

    season_values = squad_values_for_season(season_code(results_season_start(as_of)))
    logger.info("fitting Dixon-Coles on %d matches (xi=%.4f)...", len(dated), xi)
    ratings = fit_shrunk_ratings(dated, xi=xi, reference=as_of, season_values=season_values)

    refresh_connection()
    if not force:
        for existing in ModelRun.objects.filter(
            version=SERVE_VERSION, as_of_date=as_of, n_matches=len(dated)
        ).order_by("-id"):
            if run_matches_ratings(existing, ratings, xi=xi):
                return RefitOutcome(existing, False, len(dated), ratings, xi, len(season_values))

    run = save_model_run(
        ratings,
        xi=xi,
        n_matches=len(dated),
        as_of_date=as_of,
        version=SERVE_VERSION,
        notes="scheduled refit on full history",
    )
    return RefitOutcome(run, True, len(dated), ratings, xi, len(season_values))
