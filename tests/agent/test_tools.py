"""Tests for tool dispatch and the prediction service (no LLM, no DB)."""

from __future__ import annotations

from datetime import date

import numpy as np

from bundespredict.agent.adjustments import Adjustment
from bundespredict.agent.service import PredictionService, UnknownTeamError
from bundespredict.agent.tools import TOOL_SPECS, dispatch
from bundespredict.data.weather import WeatherProvider, WeatherReport
from bundespredict.model.adjust import MAGNITUDE_BOUND
from bundespredict.model.dixon_coles import TeamRatings


def _service(weather_provider: WeatherProvider | None = None) -> PredictionService:
    ratings = TeamRatings(
        teams=("strong", "weak"),
        attack=np.array([0.5, -0.5]),
        defense=np.array([-0.3, 0.3]),
        home_adv=0.25,
        rho=-0.12,
        log_likelihood=0.0,
    )
    return PredictionService(ratings, weather_provider=weather_provider)


# --- tool specs -----------------------------------------------------------


def test_tool_specs_cover_every_tool() -> None:
    names = {spec["name"] for spec in TOOL_SPECS}
    assert names == {
        "predict_match",
        "predict_match_with_context",
        "get_team_form",
        "lookup_player",
        "get_recent_results",
        "get_upcoming_fixtures",
        "get_weather",
    }


def test_no_tool_accepts_a_probability() -> None:
    # Guardrail: the LLM can never write a probability directly. No tool input
    # schema should expose a p_home/p_draw/p_away-style field.
    for spec in TOOL_SPECS:
        props = spec["input_schema"]["properties"]
        assert not any(key.startswith("p_") for key in props)


# --- predict_match --------------------------------------------------------


def test_predict_match_returns_distribution() -> None:
    out = dispatch("predict_match", {"home": "strong", "away": "weak"}, _service())
    assert not out.is_error
    total = out.payload["p_home"] + out.payload["p_draw"] + out.payload["p_away"]
    assert abs(total - 1.0) < 1e-3


def test_unknown_team_is_a_recoverable_error() -> None:
    out = dispatch("predict_match", {"home": "atlantis", "away": "weak"}, _service())
    assert out.is_error
    assert out.payload["error"] == "unknown team"
    assert "strong" in out.payload["known_teams"]


# --- predict_match_with_context ------------------------------------------


def test_context_returns_baseline_and_adjusted() -> None:
    out = dispatch(
        "predict_match_with_context",
        {
            "home": "strong",
            "away": "weak",
            "adjustments": [
                {
                    "factor": "player_out",
                    "team": "home",
                    "target": "home_attack",
                    "magnitude_xg": -0.3,
                    "confidence": "med",
                    "rationale": "striker suspended",
                }
            ],
        },
        _service(),
    )
    assert not out.is_error
    assert "baseline" in out.payload and "adjusted" in out.payload
    # Weakening the home attack lowers its win probability vs baseline.
    assert out.payload["adjusted"]["p_home"] < out.payload["baseline"]["p_home"]


def test_context_echoes_clamped_effective_magnitude() -> None:
    out = dispatch(
        "predict_match_with_context",
        {
            "home": "strong",
            "away": "weak",
            "adjustments": [
                {
                    "factor": "player_out",
                    "team": "home",
                    "target": "home_attack",
                    "magnitude_xg": -5.0,
                    "confidence": "high",
                    "rationale": "absurd request",
                }
            ],
        },
        _service(),
    )
    applied = out.payload["applied_adjustments"][0]
    assert applied["requested_magnitude_xg"] == -5.0
    assert applied["effective_magnitude_xg"] == -MAGNITUDE_BOUND


def test_malformed_adjustment_is_rejected_not_executed() -> None:
    out = dispatch(
        "predict_match_with_context",
        {
            "home": "strong",
            "away": "weak",
            "adjustments": [
                {
                    "factor": "not_a_factor",
                    "target": "home_attack",
                    "magnitude_xg": -0.3,
                    "confidence": "med",
                    "rationale": "bad",
                }
            ],
        },
        _service(),
    )
    assert out.is_error
    assert out.payload["error"] == "malformed adjustment"


def test_empty_adjustments_reproduce_baseline() -> None:
    out = dispatch(
        "predict_match_with_context",
        {"home": "strong", "away": "weak", "adjustments": []},
        _service(),
    )
    assert out.payload["adjusted"]["p_home"] == out.payload["baseline"]["p_home"]


# --- lookup_player --------------------------------------------------------


def test_lookup_player_found_and_not_found() -> None:
    found = dispatch("lookup_player", {"name": "Harry Kane"}, _service())
    assert found.payload["found"] is True
    assert found.payload["is_penalty_taker"] is True

    missing = dispatch("lookup_player", {"name": "Nobody"}, _service())
    assert missing.payload["found"] is False


# --- get_weather ----------------------------------------------------------


def test_weather_available_is_serialized() -> None:
    report = WeatherReport(
        team="strong",
        city="Somewhere",
        date=date(2026, 8, 29),
        temperature_c=31.2,
        wind_kmh=34.6,
        precip_mm=0.0,
    )
    out = dispatch(
        "get_weather",
        {"team": "strong", "date": "2026-08-29"},
        _service(lambda team, on: report),
    )
    assert not out.is_error
    assert out.payload["available"] is True
    assert out.payload["city"] == "Somewhere"
    assert out.payload["wind_kmh"] == 34.6


def test_weather_unavailable_when_provider_returns_none() -> None:
    out = dispatch("get_weather", {"team": "strong"}, _service(lambda team, on: None))
    assert not out.is_error
    assert out.payload["available"] is False


def test_weather_provider_receives_requested_date() -> None:
    seen: list[date] = []

    def provider(team: str, on: date) -> WeatherReport | None:
        seen.append(on)
        return None

    dispatch("get_weather", {"team": "strong", "date": "2026-08-29"}, _service(provider))
    assert seen == [date(2026, 8, 29)]


def test_weather_bad_date_is_a_recoverable_error() -> None:
    out = dispatch(
        "get_weather", {"team": "strong", "date": "not-a-date"}, _service(lambda t, o: None)
    )
    assert out.is_error


def test_prompt_mentions_the_weather_tool() -> None:
    from bundespredict.agent.prompt import build_system_prompt

    prompt = build_system_prompt(("strong", "weak"))
    assert "get_weather" in prompt


# --- service-level --------------------------------------------------------


def test_service_records_last_prediction() -> None:
    service = _service()
    service.predict_match("strong", "weak")
    assert service.last_prediction is not None
    assert service.last_prediction.adjusted is None

    service.predict_with_context(
        "strong",
        "weak",
        [
            Adjustment(
                factor="player_out",
                team="home",
                target="home_attack",
                magnitude_xg=-0.2,
                confidence="med",
                rationale="x",
            )
        ],
    )
    assert service.last_prediction.adjusted is not None
    assert service.last_prediction.served is service.last_prediction.adjusted


def test_team_form_without_session_raises() -> None:
    service = _service()
    try:
        service.team_form("strong")
    except RuntimeError as exc:
        assert "session" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_require_team_raises_unknown() -> None:
    service = _service()
    try:
        service.predict_match("ghost", "weak")
    except UnknownTeamError as exc:
        assert str(exc) == "ghost"
    else:  # pragma: no cover
        raise AssertionError("expected UnknownTeamError")
