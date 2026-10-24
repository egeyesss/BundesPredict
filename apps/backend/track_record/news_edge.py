"""Checking chats that brought news before kickoff against where the market later moved.

Every agent answer is already stored in `predictions` with its pre-adjustment baseline, so a chat
that brought news is a row with applied adjustments created before the fixture kicked off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
from django.db.models import F, Func, IntegerField

from bundespredict.eval.market import devig
from football.models import Fixture, Match
from predictions.models import Prediction

from .scoring import OUTCOME_LETTERS

MIN_CHATS_FOR_RATE = 20
# Lines open early in the week; a chat weeks ahead has no market to be compared with.
NEWS_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class Verdict:
    ahead: bool
    reason: str


def edge_verdict(*, opening: float, agent: float, closing: float) -> Verdict:
    """Ahead means the agent moved the way the market later did and landed nearer the close.

    The distances are compared on the outcome the news was about, as probabilities.
    """
    market_move = closing - opening
    agent_move = agent - opening
    if market_move == 0:
        return Verdict(False, "market didn't move")
    if agent_move == 0:
        return Verdict(False, "agent stayed on the opening line")
    if (agent_move > 0) != (market_move > 0):
        return Verdict(False, "market went the other way")
    if abs(agent - closing) < abs(market_move):
        return Verdict(True, "ahead of the market")
    return Verdict(False, "overshot the market")


def _devigged(odds: tuple[float | None, float | None, float | None]) -> list[float] | None:
    if any(price is None or price <= 1.0 for price in odds):
        return None
    return [float(p) for p in devig(np.array(odds, dtype=np.float64))]


def _line(match: Match | None, *, closing: bool) -> list[float] | None:
    if match is None:
        return None
    columns = ("avgc_", "b365c_") if closing else ("avg_", "b365_")
    for prefix in columns:
        probs = _devigged(
            tuple(getattr(match, f"{prefix}{side}") for side in ("home", "draw", "away"))
        )
        if probs is not None:
            return probs
    return None


def _news_outcome(prediction: Prediction) -> int:
    """The outcome whose probability the news moved the most."""
    base = (prediction.base_p_home, prediction.base_p_draw, prediction.base_p_away)
    served = (prediction.p_home, prediction.p_draw, prediction.p_away)
    return int(np.argmax([abs(s - b) for s, b in zip(served, base, strict=True)]))


def build_news_edge() -> dict[str, Any]:
    predictions = (
        Prediction.objects.annotate(
            adjustment_count=Func(
                F("adjustments_json"), function="json_array_length", output_field=IntegerField()
            )
        )
        .filter(adjustment_count__gt=0)
        .select_related("home", "away")
        .order_by("created_at", "id")
    )
    chats: list[dict[str, Any]] = []
    for prediction in predictions:
        fixture = (
            Fixture.objects.filter(
                home_id=prediction.home_id,
                away_id=prediction.away_id,
                kickoff_utc__gt=prediction.created_at,
                kickoff_utc__lte=prediction.created_at + NEWS_WINDOW,
            )
            .order_by("kickoff_utc")
            .first()
        )
        if fixture is None:
            continue
        match = Match.objects.filter(
            season=fixture.season, home_id=fixture.home_id, away_id=fixture.away_id
        ).first()
        opening, closing = _line(match, closing=False), _line(match, closing=True)
        outcome = _news_outcome(prediction)
        agent = (prediction.p_home, prediction.p_draw, prediction.p_away)[outcome]

        row: dict[str, Any] = {
            "prediction_id": prediction.id,
            "fixture_id": fixture.id,
            "matchday": fixture.matchday,
            "kickoff_utc": fixture.kickoff_utc,
            "logged_at": prediction.created_at,
            "hours_before_kickoff": (fixture.kickoff_utc - prediction.created_at).total_seconds()
            / 3600,
            "home": {"name": fixture.home.name, "code": fixture.home.code},
            "away": {"name": fixture.away.name, "code": fixture.away.code},
            "outcome": OUTCOME_LETTERS[outcome],
            "agent": agent,
            "opening": opening[outcome] if opening and closing else None,
            "closing": closing[outcome] if opening and closing else None,
            "ahead": None,
            "verdict": "waiting for the closing line",
        }
        if opening and closing:
            verdict = edge_verdict(opening=opening[outcome], agent=agent, closing=closing[outcome])
            row["ahead"], row["verdict"] = verdict.ahead, verdict.reason
        chats.append(row)

    compared = [row for row in chats if row["ahead"] is not None]
    ahead = sum(1 for row in compared if row["ahead"])
    return {
        "n_logged": len(chats),
        "n_compared": len(compared),
        "n_ahead": ahead,
        "minimum_for_rate": MIN_CHATS_FOR_RATE,
        "rate": ahead / len(compared) if len(compared) >= MIN_CHATS_FOR_RATE else None,
        "chats": chats,
    }
