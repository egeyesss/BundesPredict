"""Read queries over the football tables that the API and the agent share.

Anything that feeds a prediction takes an explicit cutoff (`as_of` or `as_of_date`) instead of
reading the clock, so a prediction for a given date can never see data from after it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

import numpy as np
from django.db.models import F, Q

from bundespredict.data.fixtures import UpcomingFixture
from bundespredict.data.form import FormMatch, TeamForm
from bundespredict.data.players import PlayerRow
from bundespredict.data.results import ResultRow
from bundespredict.model.dixon_coles import TeamRatings

from .models import Fixture, Match, ModelRun, Player, Team, TeamAlias, TeamParam

FixtureScope = Literal["next_matchday", "week"]

WEEK = timedelta(days=7)


def latest_model_run(
    *, as_of_date: date | None = None, version: str | None = None
) -> ModelRun | None:
    """The most recently trained run, or the newest run written for the cutoff `as_of_date`.

    Walk-forward backtests write one run per cutoff, so passing the cutoff selects the run fit
    on matches strictly before that date. `version` limits the search to one kind of run
    (`"serve"` for the fits that answer requests, `"walk-forward"` for backtest cutoffs).
    """
    runs = ModelRun.objects.order_by("-trained_at", "-id")
    if as_of_date is not None:
        runs = runs.filter(as_of_date=as_of_date)
    if version is not None:
        runs = runs.filter(version=version)
    return runs.first()


def team_params_for(run: ModelRun) -> list[TeamParam]:
    """Every team's attack and defense strengths in `run`, ordered by team name.

    No cutoff is needed because the run already fixes which data the parameters saw.
    """
    return list(
        TeamParam.objects.filter(model_run=run).select_related("team").order_by("team__name")
    )


def ratings_for(run: ModelRun) -> TeamRatings:
    """The run's stored parameters as the engine's `TeamRatings`, teams sorted by name."""
    params = team_params_for(run)
    return TeamRatings(
        teams=tuple(param.team.name for param in params),
        attack=np.array([param.attack for param in params], dtype=np.float64),
        defense=np.array([param.defense for param in params], dtype=np.float64),
        home_adv=run.home_adv,
        rho=run.rho,
        log_likelihood=run.log_likelihood,
        xg_coef=run.xg_coef,
    )


def upcoming_fixtures(scope: FixtureScope, as_of: datetime) -> list[Fixture]:
    """Fixtures still to be played at `as_of`, ordered by kickoff.

    `next_matchday` returns the whole matchday that contains the first fixture kicking off at or
    after `as_of`, including games of that matchday that have already started. `week` returns
    fixtures kicking off in `[as_of, as_of + 7 days)`.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")

    fixtures = Fixture.objects.select_related("home", "away").order_by("kickoff_utc", "id")
    if scope == "week":
        return list(fixtures.filter(kickoff_utc__gte=as_of, kickoff_utc__lt=as_of + WEEK))

    next_fixture = fixtures.filter(kickoff_utc__gte=as_of).first()
    if next_fixture is None:
        return []
    return list(fixtures.filter(season=next_fixture.season, matchday=next_fixture.matchday))


def resolve_team(name_or_alias: str) -> Team | None:
    """The team for a canonical name or a source alias, or `None` when nothing matches.

    An exact canonical name beats an exact alias, which beats a case-insensitive match on either.
    """
    needle = name_or_alias.strip()
    exact = Team.objects.filter(name=needle).first()
    if exact is not None:
        return exact
    alias = TeamAlias.objects.filter(alias=needle).select_related("team").first()
    if alias is not None:
        return alias.team
    loose = Team.objects.filter(name__iexact=needle).first()
    if loose is not None:
        return loose
    loose_alias = TeamAlias.objects.filter(alias__iexact=needle).select_related("team").first()
    return loose_alias.team if loose_alias is not None else None


def team_form(team: Team, as_of: date | None, *, n: int = 5) -> TeamForm:
    """The team's last `n` results strictly before `as_of`, newest first.

    `as_of=None` means no cutoff, which is what a request without a match date gets. A team with
    no earlier matches (a newcomer at the start of a season) gets an empty form.
    """
    matches_of_team = Match.objects.filter(Q(home=team) | Q(away=team))
    if as_of is not None:
        matches_of_team = matches_of_team.filter(date__lt=as_of)
    played = matches_of_team.select_related("home", "away").order_by("-date", "-id")[:n]

    matches: list[FormMatch] = []
    for match in played:
        at_home = match.home_id == team.id
        goals_for = match.home_goals if at_home else match.away_goals
        goals_against = match.away_goals if at_home else match.home_goals
        opponent = match.away if at_home else match.home
        matches.append(
            FormMatch(
                date=match.date,
                opponent=opponent.name,
                venue="H" if at_home else "A",
                goals_for=goals_for,
                goals_against=goals_against,
                result=_result(goals_for, goals_against),
            )
        )

    wins = sum(m.result == "W" for m in matches)
    draws = sum(m.result == "D" for m in matches)
    return TeamForm(
        team=team.name,
        played=len(matches),
        wins=wins,
        draws=draws,
        losses=len(matches) - wins - draws,
        points=3 * wins + draws,
        goals_for=sum(m.goals_for for m in matches),
        goals_against=sum(m.goals_against for m in matches),
        matches=tuple(matches),
    )


def _result(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "W"
    if goals_for < goals_against:
        return "L"
    return "D"


def latest_result_date() -> date | None:
    """Date of the most recent completed match, or `None` on an empty table."""
    return Match.objects.order_by("-date").values_list("date", flat=True).first()


def recent_results(as_of: date | None, *, n: int = 9) -> tuple[ResultRow, ...]:
    """The last `n` completed matches league-wide strictly before `as_of`, newest first."""
    matches = Match.objects.select_related("home", "away")
    if as_of is not None:
        matches = matches.filter(date__lt=as_of)
    return tuple(
        ResultRow(
            date=match.date,
            season=match.season,
            home=match.home.name,
            away=match.away.name,
            home_goals=match.home_goals,
            away_goals=match.away_goals,
        )
        for match in matches.order_by("-date", "-id")[:n]
    )


def scheduled_fixtures(
    on_or_after: date, *, team: Team | None = None, n: int = 9
) -> tuple[UpcomingFixture, ...]:
    """The next `n` fixtures kicking off from the start of `on_or_after`, soonest first.

    `team` narrows the list to one club's schedule.
    """
    fixtures = Fixture.objects.select_related("home", "away").filter(
        kickoff_utc__gte=datetime.combine(on_or_after, time.min, tzinfo=UTC)
    )
    if team is not None:
        fixtures = fixtures.filter(Q(home=team) | Q(away=team))
    return tuple(
        UpcomingFixture(
            kickoff_utc=fixture.kickoff_utc,
            matchday=fixture.matchday,
            season=fixture.season,
            home=fixture.home.name,
            away=fixture.away.name,
        )
        for fixture in fixtures.order_by("kickoff_utc", "id")[:n]
    )


def player_rows() -> list[PlayerRow]:
    """Every stored squad member as `(name, team, position, value, scraped_at)`, richest first."""
    players = Player.objects.select_related("team").order_by(
        F("market_value_eur").desc(nulls_last=True)
    )
    return [(p.name, p.team.name, p.position, p.market_value_eur, p.scraped_at) for p in players]
