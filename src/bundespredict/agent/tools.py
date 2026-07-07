"""Tool definitions and dispatch for the agent loop.

Four tools sit between the LLM and the deterministic engine
(:class:`~bundespredict.agent.service.PredictionService`):

* ``predict_match`` — baseline distribution for a fixture.
* ``predict_match_with_context`` — the override path: apply bounded adjustments
  and recompute.
* ``get_team_form`` — recent results, so the LLM grounds claims in data.
* ``lookup_player`` — a seeded player's role/importance, to size a player
  adjustment.

The crucial guardrails live in :func:`dispatch`: adjustment arguments are
validated through the :class:`Adjustment` schema (a malformed one is *rejected*,
not executed), there is **no tool that accepts a probability**, and every
magnitude is clamped by the engine regardless of what the LLM asked. The tool
input schemas enumerate the same literals the Pydantic models do — derived from
them here so the two can't drift.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, get_args

from pydantic import ValidationError

from bundespredict.data.form import TeamForm
from bundespredict.data.weather import WeatherReport
from bundespredict.model.adjust import clamp_magnitude
from bundespredict.model.markets import Markets

from .adjustments import Adjustment, Confidence, Factor, Side, Target
from .players import PlayerInfo
from .service import PredictionService, UnknownTeamError

# Anthropic tool spec is a list of {name, description, input_schema} dicts.
ToolSpec = dict[str, Any]


def _enum(literal: Any) -> list[str]:
    """JSON-schema ``enum`` list straight from a typing ``Literal`` (no drift)."""
    return list(get_args(literal))


_ADJUSTMENT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "factor": {"type": "string", "enum": _enum(Factor)},
        "team": {
            "type": "string",
            "enum": _enum(Side),
            "description": "side affected; omit for match-level",
        },
        "target": {
            "type": "string",
            "enum": _enum(Target),
            "description": "what it modifies in the engine",
        },
        "magnitude_xg": {
            "type": "number",
            "description": "signed expected-goals delta; clamped to +/-0.6 by the engine",
        },
        "confidence": {"type": "string", "enum": _enum(Confidence)},
        "rationale": {"type": "string", "description": "one human-readable line, shown in the UI"},
    },
    "required": ["factor", "target", "magnitude_xg", "confidence", "rationale"],
    "additionalProperties": False,
}

TOOL_SPECS: list[ToolSpec] = [
    {
        "name": "predict_match",
        "description": (
            "Baseline match prediction from the fitted model: 1X2 probabilities, "
            "over/under and BTTS, expected goals, and the most likely scorelines. "
            "Use this first, before applying any context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "home": {"type": "string", "description": "canonical home team name"},
                "away": {"type": "string", "description": "canonical away team name"},
            },
            "required": ["home", "away"],
            "additionalProperties": False,
        },
    },
    {
        "name": "predict_match_with_context",
        "description": (
            "Re-run the prediction after applying a list of bounded expected-goals "
            "adjustments (e.g. a striker out, a reduced crowd). Returns both the "
            "baseline and the adjusted distribution plus the effective magnitudes "
            "actually applied. You do not set probabilities — only adjustments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "home": {"type": "string", "description": "canonical home team name"},
                "away": {"type": "string", "description": "canonical away team name"},
                "adjustments": {
                    "type": "array",
                    "items": _ADJUSTMENT_ITEM_SCHEMA,
                    "description": "the contextual adjustments to apply",
                },
            },
            "required": ["home", "away", "adjustments"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_team_form",
        "description": (
            "A team's recent results before the match date: record, points, goals "
            "for/against, and the last few games. Use it to ground claims about form."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "canonical team name"},
                "n": {"type": "integer", "description": "how many recent matches (default 5)"},
            },
            "required": ["team"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lookup_player",
        "description": (
            "Look up a player's position, penalty-taker status, and importance "
            "to help size an availability adjustment. Importance is derived from "
            "the player's market-value standing within his own squad (top ~20% = "
            "high, next ~30% = medium, rest = low), not hand-labelled. The result "
            "includes scraped_at — treat a snapshot older than a few weeks as "
            "possibly stale (transfers). Returns not-found for unknown players — "
            "fall back to the knowledge-base ranges then."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "player name"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recent_results",
        "description": (
            "The league's most recent completed matches (date, teams, final score), "
            "newest first. Use it for questions about the latest round or how recent "
            "games went, and to see how fresh the results data is."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "how many matches (default 9, one round)"}
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Match-day weather forecast at the home team's stadium: max "
            "temperature (C), max wind (km/h), and precipitation (mm). Use it to "
            "CHECK conditions before applying a weather adjustment instead of "
            "trusting a claim. Forecasts only reach ~16 days ahead; a match "
            "further out, an unknown venue, or a fetch failure returns "
            "available:false, and you should then rely on the user's stated "
            "conditions or skip the weather factor. The model never sees "
            "weather — this only grounds whether a weather factor applies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "canonical home team name (the venue)",
                },
                "date": {
                    "type": "string",
                    "description": "match day as YYYY-MM-DD; defaults to today",
                },
            },
            "required": ["team"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_upcoming_fixtures",
        "description": (
            "The scheduled upcoming fixtures (kickoff, matchday, teams), soonest "
            "first, optionally for one team. Use it to resolve 'their next game' to a "
            "concrete opponent, venue, and date before predicting. An empty list means "
            "no schedule is loaded for the period, not that no matches will happen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "canonical team name (optional)"},
                "n": {"type": "integer", "description": "how many fixtures (default 9)"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]


@dataclass(frozen=True)
class ToolOutcome:
    """The result of one tool call, ready to become a tool_result block."""

    payload: dict[str, Any]
    is_error: bool = False

    def to_json(self) -> str:
        return json.dumps(self.payload)


def _round(value: float, places: int = 4) -> float:
    return round(value, places)


def markets_to_dict(m: Markets) -> dict[str, Any]:
    """Serialize a market distribution for a tool result (rounded for the LLM)."""
    return {
        "p_home": _round(m.p_home),
        "p_draw": _round(m.p_draw),
        "p_away": _round(m.p_away),
        "p_over_2_5": _round(m.p_over_2_5),
        "p_under_2_5": _round(m.p_under_2_5),
        "p_btts": _round(m.p_btts),
        "exp_home_goals": _round(m.exp_home_goals, 2),
        "exp_away_goals": _round(m.exp_away_goals, 2),
        "top_scores": [{"home": h, "away": a, "p": _round(p)} for h, a, p in m.top_scores],
    }


def form_to_dict(form: TeamForm) -> dict[str, Any]:
    return {
        "team": form.team,
        "played": form.played,
        "record": f"{form.wins}-{form.draws}-{form.losses}",
        "points": form.points,
        "goals_for": form.goals_for,
        "goals_against": form.goals_against,
        "recent": [
            {
                "date": m.date.isoformat(),
                "opponent": m.opponent,
                "venue": m.venue,
                "score": f"{m.goals_for}-{m.goals_against}",
                "result": m.result,
            }
            for m in form.matches
        ],
    }


def player_to_dict(player: PlayerInfo) -> dict[str, Any]:
    out: dict[str, Any] = {
        "found": True,
        "name": player.name,
        "team": player.team,
        "role": player.role,
        "is_penalty_taker": player.is_penalty_taker,
        "importance": player.importance,
    }
    # Present only for scraped players; the seeded fallback has neither.
    if player.market_value_eur is not None:
        out["market_value_eur"] = player.market_value_eur
    if player.scraped_at is not None:
        out["scraped_at"] = player.scraped_at.date().isoformat()
    return out


def weather_to_dict(report: WeatherReport) -> dict[str, Any]:
    return {
        "available": True,
        "team": report.team,
        "city": report.city,
        "date": report.date.isoformat(),
        "temperature_c": _round(report.temperature_c, 1),
        "wind_kmh": _round(report.wind_kmh, 1),
        "precip_mm": _round(report.precip_mm, 1),
    }


def _applied_adjustment(adj: Adjustment) -> dict[str, Any]:
    """One adjustment as echoed back: requested vs. effective (clamped) magnitude."""
    return {
        "factor": adj.factor,
        "team": adj.team,
        "target": adj.target,
        "requested_magnitude_xg": adj.magnitude_xg,
        "effective_magnitude_xg": clamp_magnitude(adj.magnitude_xg),
        "confidence": adj.confidence,
        "rationale": adj.rationale,
    }


def dispatch(name: str, tool_input: dict[str, Any], service: PredictionService) -> ToolOutcome:
    """Execute one tool call and return a serializable outcome.

    Errors the LLM can recover from (an unknown team, a malformed adjustment)
    come back as ``is_error`` outcomes so the model can correct itself on the next
    turn, rather than raising and aborting the whole conversation.
    """
    try:
        if name == "predict_match":
            markets = service.predict_match(tool_input["home"], tool_input["away"])
            return ToolOutcome(markets_to_dict(markets))

        if name == "predict_match_with_context":
            try:
                adjustments = [Adjustment(**item) for item in tool_input["adjustments"]]
            except ValidationError as exc:
                return ToolOutcome(
                    {"error": "malformed adjustment", "detail": exc.errors(include_url=False)},
                    is_error=True,
                )
            adjusted = service.predict_with_context(
                tool_input["home"], tool_input["away"], adjustments
            )
            record = service.last_prediction
            assert record is not None  # predict_with_context always sets it
            return ToolOutcome(
                {
                    "baseline": markets_to_dict(record.baseline),
                    "adjusted": markets_to_dict(adjusted),
                    "applied_adjustments": [_applied_adjustment(a) for a in adjustments],
                }
            )

        if name == "get_team_form":
            form = service.team_form(tool_input["team"], n=tool_input.get("n", 5))
            return ToolOutcome(form_to_dict(form))

        if name == "lookup_player":
            player = service.lookup_player(tool_input["name"])
            if player is None:
                return ToolOutcome({"found": False, "name": tool_input["name"]})
            return ToolOutcome(player_to_dict(player))

        if name == "get_recent_results":
            results = service.recent_results(n=tool_input.get("n", 9))
            return ToolOutcome(
                {
                    "results": [
                        {
                            "date": r.date.isoformat(),
                            "home": r.home,
                            "away": r.away,
                            "score": f"{r.home_goals}-{r.away_goals}",
                        }
                        for r in results
                    ]
                }
            )

        if name == "get_weather":
            on = tool_input.get("date")
            # An unparseable date raises ValueError -> recoverable error below,
            # so the model can retry with a valid YYYY-MM-DD.
            on_date = date.fromisoformat(on) if on else None
            report = service.weather(tool_input["team"], on=on_date)
            if report is None:
                return ToolOutcome({"available": False, "team": tool_input["team"]})
            return ToolOutcome(weather_to_dict(report))

        if name == "get_upcoming_fixtures":
            fixtures = service.upcoming_fixtures(
                team=tool_input.get("team"), n=tool_input.get("n", 9)
            )
            return ToolOutcome(
                {
                    "fixtures": [
                        {
                            "kickoff_utc": f.kickoff_utc.isoformat() + "Z",
                            "matchday": f.matchday,
                            "home": f.home,
                            "away": f.away,
                        }
                        for f in fixtures
                    ]
                }
            )

    except UnknownTeamError as exc:
        return ToolOutcome(
            {"error": "unknown team", "team": str(exc), "known_teams": list(service.teams)},
            is_error=True,
        )
    except ValueError as exc:
        return ToolOutcome({"error": str(exc)}, is_error=True)

    return ToolOutcome({"error": f"unknown tool: {name}"}, is_error=True)
