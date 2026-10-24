"""Assembling the public track record from frozen predictions, resolutions and closing odds."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from bundespredict.eval.market import devig
from football.models import Match

from .backtest_summary import BACKTEST
from .models import FixturePrediction, Resolution
from .news_edge import build_news_edge
from .scoring import (
    BASE_RATE,
    Forecast,
    Summary,
    calibration_bins,
    outcome_index,
    score_forecast,
    summarize,
)


@dataclass(frozen=True)
class ScoredFixture:
    resolution: Resolution
    model: Forecast
    market: Forecast | None
    base_rate: Forecast


def _closing_odds(match: Match | None) -> tuple[float, float, float] | None:
    if match is None:
        return None
    for odds in (
        (match.avgc_home, match.avgc_draw, match.avgc_away),
        (match.b365c_home, match.b365c_draw, match.b365c_away),
    ):
        if all(price is not None and price > 1.0 for price in odds):
            return (float(odds[0]), float(odds[1]), float(odds[2]))  # type: ignore[arg-type]
    return None


def _market_probs(odds: tuple[float, float, float]) -> tuple[float, float, float]:
    home, draw, away = devig(np.array(odds, dtype=np.float64))
    return (float(home), float(draw), float(away))


def _summary_dict(summary: Summary | None) -> dict[str, Any] | None:
    return asdict(summary) if summary else None


def _scored_fixtures(season: str) -> list[ScoredFixture]:
    resolutions = list(
        Resolution.objects.filter(prediction__fixture__season=season)
        .select_related("prediction__fixture__home", "prediction__fixture__away")
        .order_by("prediction__fixture__kickoff_utc", "prediction__fixture_id")
    )
    matches = {
        (match.home_id, match.away_id): match for match in Match.objects.filter(season=season)
    }
    scored = []
    for resolution in resolutions:
        prediction = resolution.prediction
        fixture = prediction.fixture
        outcome = outcome_index(resolution.home_goals, resolution.away_goals)
        odds = _closing_odds(matches.get((fixture.home_id, fixture.away_id)))
        scored.append(
            ScoredFixture(
                resolution=resolution,
                model=Forecast((prediction.p_home, prediction.p_draw, prediction.p_away), outcome),
                market=Forecast(_market_probs(odds), outcome) if odds else None,
                base_rate=Forecast(BASE_RATE, outcome),
            )
        )
    return scored


def _fixture_row(item: ScoredFixture) -> dict[str, Any]:
    prediction = item.resolution.prediction
    fixture = prediction.fixture
    score = score_forecast(item.model)
    return {
        "fixture_id": fixture.id,
        "kickoff_utc": fixture.kickoff_utc,
        "home": {"name": fixture.home.name, "code": fixture.home.code},
        "away": {"name": fixture.away.name, "code": fixture.away.code},
        "home_goals": item.resolution.home_goals,
        "away_goals": item.resolution.away_goals,
        "outcome": item.resolution.outcome,
        "p_home": prediction.p_home,
        "p_draw": prediction.p_draw,
        "p_away": prediction.p_away,
        "rps": score.rps,
        "hit": score.hit,
    }


def _market_forecasts(items: Sequence[ScoredFixture]) -> list[Forecast]:
    return [item.market for item in items if item.market is not None]


def _matchday_rows(season: str, items: list[ScoredFixture]) -> list[dict[str, Any]]:
    frozen: defaultdict[int, int] = defaultdict(int)
    for matchday in FixturePrediction.objects.filter(fixture__season=season).values_list(
        "fixture__matchday", flat=True
    ):
        frozen[matchday] += 1
    resolved: dict[int, list[ScoredFixture]] = defaultdict(list)
    for item in items:
        resolved[item.resolution.prediction.fixture.matchday].append(item)

    rows = []
    for matchday in sorted(frozen, reverse=True):
        group = resolved[matchday]
        model = summarize([item.model for item in group])
        market = summarize(_market_forecasts(group))
        base = summarize([item.base_rate for item in group])
        rows.append(
            {
                "season": season,
                "matchday": matchday,
                "n_fixtures": frozen[matchday],
                "n_resolved": len(group),
                "rps": model.rps if model else None,
                "log_loss": model.log_loss if model else None,
                "hit_rate": model.hit_rate if model else None,
                "bookmaker_rps": market.rps if market else None,
                "base_rate_rps": base.rps if base else None,
                "fixtures": [_fixture_row(item) for item in group],
            }
        )
    return rows


def _backtest_period() -> dict[str, Any]:
    return {
        "kind": "backtest",
        "label": BACKTEST.label,
        "since": None,
        "model": {
            "n_fixtures": BACKTEST.n_fixtures,
            "rps": BACKTEST.model_rps,
            "log_loss": BACKTEST.model_log_loss,
            "hit_rate": None,
        },
        "bookmaker": {
            "n_fixtures": BACKTEST.n_fixtures,
            "rps": BACKTEST.market_rps,
            "log_loss": BACKTEST.market_log_loss,
            "hit_rate": None,
        },
        "base_rate": None,
        "calibration_error": BACKTEST.calibration_error,
        "forecasters": [asdict(forecaster) for forecaster in BACKTEST.forecasters],
    }


def _latest_season() -> str | None:
    season = (
        FixturePrediction.objects.order_by("-fixture__season")
        .values_list("fixture__season", flat=True)
        .first()
    )
    return str(season) if season is not None else None


def build_track_record(season: str | None = None) -> dict[str, Any]:
    scope = season if season is not None else _latest_season()
    items = _scored_fixtures(scope) if scope is not None else []
    first_frozen = (
        FixturePrediction.objects.filter(fixture__season=scope)
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
        if scope is not None
        else None
    )
    since = first_frozen.date() if first_frozen else None

    live: dict[str, Any] = {
        "kind": "live",
        "label": f"Live since {since.isoformat()}" if since else "Live record",
        "since": since,
        "model": _summary_dict(summarize([item.model for item in items])),
        "bookmaker": _summary_dict(summarize(_market_forecasts(items))),
        "base_rate": _summary_dict(summarize([item.base_rate for item in items])),
        "calibration_error": None,
        "forecasters": [],
    }
    return {
        "season": season,
        "live": live,
        "backtest": _backtest_period(),
        "matchdays": _matchday_rows(scope, items) if scope is not None else [],
        "calibration": [asdict(b) for b in calibration_bins([item.model for item in items])],
        "news_edge": build_news_edge(),
    }
