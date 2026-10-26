"""The two past conversations a new demo user starts with.

The numbers come from the serving model run through the same adjustment path the agent uses, so
a seeded result card is real engine output. No LLM is involved: the adjustments are fixed
scenarios and the wording is a template over the fixture's real team names and squad data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from django.contrib.auth.models import User
from django.db import transaction

from bundespredict.agent.adjustments import Adjustment
from bundespredict.agent.loop import AgentResult
from bundespredict.agent.service import PredictionRecord, PredictionService
from bundespredict.model.adjust import MAGNITUDE_BOUND, clamp_magnitude
from chat.models import Conversation, Message
from football.models import Fixture, Player, Team
from predictions.models import Prediction
from predictions.ports import DjangoAgentPorts
from predictions.serializers import serialize_predict_response

logger = logging.getLogger(__name__)

FIXTURE_CANDIDATES = 40
ATTACKING_POSITIONS = ("Forward", "Winger", "Striker", "Attack")


@dataclass(frozen=True)
class Scenario:
    """Whose absence the chat is about (`"home"` or `"away"`) and how big the adjustment is."""

    side: Literal["home", "away"]
    requested_xg: float


# Beyond the 0.6 cap on purpose, so one card shows requested against applied.
CLAMPED = Scenario(side="home", requested_xg=-0.85)
UNCLAMPED = Scenario(side="away", requested_xg=-0.25)


def _star_of(team: Team) -> str | None:
    """The squad's most valuable forward, else its most valuable outfield player."""
    squad = list(
        Player.objects.filter(team=team)
        .order_by("-market_value_eur", "name")
        .exclude(position__icontains="Goalkeeper")
    )
    attackers = [p for p in squad if any(word in p.position for word in ATTACKING_POSITIONS)]
    chosen = attackers or squad
    return chosen[0].name if chosen else None


def _pick_fixtures(known_teams: set[str], now: datetime) -> list[Fixture]:
    """The next two fixtures between rated clubs, topped up with the latest played ones."""
    base = Fixture.objects.select_related("home", "away")
    upcoming = base.filter(kickoff_utc__gte=now).order_by("kickoff_utc", "id")
    played = base.filter(kickoff_utc__lt=now).order_by("-kickoff_utc", "-id")
    picked: list[Fixture] = []
    for queryset in (upcoming, played):
        for fixture in queryset[:FIXTURE_CANDIDATES]:
            if {fixture.home.name, fixture.away.name} <= known_teams:
                picked.append(fixture)
            if len(picked) == 2:
                return picked
    return picked


def _question(fixture: Fixture, scenario: Scenario, who: str) -> str:
    home, away = fixture.home.name, fixture.away.name
    if scenario.side == "home":
        return f"What if {who} is out for {home} against {away}?"
    return f"What if {who} misses the trip for {away} at {home}?"


def _answer(scenario: Scenario, team: str, who: str, record: PredictionRecord) -> str:
    base, served = record.baseline, record.served
    if scenario.side == "home":
        goals = (base.exp_home_goals, served.exp_home_goals)
        win = (base.p_home, served.p_home)
    else:
        goals = (base.exp_away_goals, served.exp_away_goals)
        win = (base.p_away, served.p_away)
    asked = record.adjustments[0].magnitude_xg
    applied = clamp_magnitude(asked)
    if applied != asked:
        cap_note = (
            f"I asked for {asked:+.2f} xG, but a single adjustment is capped at "
            f"{MAGNITUDE_BOUND:.2f}, so {applied:+.2f} was applied."
        )
    else:
        cap_note = f"That is a {asked:+.2f} xG adjustment, inside the {MAGNITUDE_BOUND:.2f} cap."
    return (
        f"Taking {who} out lowers {team}'s expected goals from {goals[0]:.2f} to {goals[1]:.2f}. "
        f"{cap_note} {team}'s win probability moves from {win[0]:.0%} to {win[1]:.0%}."
    )


def _seed_one(
    user: User,
    ports: DjangoAgentPorts,
    service: PredictionService,
    run_id: int,
    fixture: Fixture,
    scenario: Scenario,
) -> Conversation:
    home, away = fixture.home, fixture.away
    team = home if scenario.side == "home" else away
    who = _star_of(team) or f"{team.name}'s first-choice striker"
    question = _question(fixture, scenario, who)
    adjustment = Adjustment(
        factor="player_out",
        team=scenario.side,
        target="home_attack" if scenario.side == "home" else "away_attack",
        magnitude_xg=scenario.requested_xg,
        confidence="med",
        rationale=f"Scenario: {who} unavailable, which takes {team.name}'s main goal threat out.",
    )
    service.predict_with_context(home.name, away.name, [adjustment])
    record = service.last_prediction
    assert record is not None
    answer = _answer(scenario, team.name, who, record)

    conversation = Conversation.objects.create(
        user=user, title=Conversation.title_for(f"If {who} is out"), fixture=fixture
    )
    prediction_id = ports.save(
        model_run_id=run_id, record=record, explanation=answer, query=question, match_date=None
    )
    payload = serialize_predict_response(
        AgentResult(query=question, explanation=answer, record=record), prediction_id
    )
    Prediction.objects.filter(pk=prediction_id).update(
        user=user, conversation=conversation, response_json=payload
    )
    Message.objects.create(conversation=conversation, role="user", content=question)
    Message.objects.create(
        conversation=conversation, role="assistant", content=answer, prediction_id=prediction_id
    )
    return conversation


def seed_conversations(user: User, *, now: datetime) -> list[Conversation]:
    """Two saved chats on real fixtures, one with a clamped adjustment and one without."""
    ports = DjangoAgentPorts()
    serving = ports.latest_ratings()
    if serving is None:
        logger.warning("No serving model run; demo user %s starts without seeded chats", user.pk)
        return []
    service = PredictionService(serving.ratings)
    fixtures = _pick_fixtures(set(serving.ratings.teams), now)
    with transaction.atomic():
        return [
            _seed_one(user, ports, service, serving.run_id, fixture, scenario)
            for fixture, scenario in zip(fixtures, (CLAMPED, UNCLAMPED), strict=False)
        ]
