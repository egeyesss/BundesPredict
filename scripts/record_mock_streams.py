"""Regenerate the recorded mock data under apps/web/lib/api/mocks/recorded/.

The web mocks replay real engine output: the 18 current clubs get fixed, plausible ratings, the
agent loop runs scripted tool-call transcripts (the same shape as tests/agent/fakes.py) against
the real engine and the real FastAPI response builder, and every SSE frame is written as JSON.
Nothing here calls the network or an LLM, so the output is deterministic.

    uv run python scripts/record_mock_streams.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps" / "api")]

from tests.agent.fakes import (  # noqa: E402
    FakeResponse,
    FakeTextBlock,
    FakeToolUseBlock,
    ScriptedClient,
)

from app.schemas import build_response  # noqa: E402
from bundespredict.agent.adjustments import Adjustment  # noqa: E402
from bundespredict.agent.loop import AgentEvent, run_agent_events  # noqa: E402
from bundespredict.agent.service import PredictionService  # noqa: E402
from bundespredict.agent.tools import markets_to_dict  # noqa: E402
from bundespredict.data.fixtures import UpcomingFixture  # noqa: E402
from bundespredict.data.form import FormMatch, TeamForm  # noqa: E402
from bundespredict.data.weather import WeatherReport  # noqa: E402
from bundespredict.model.dixon_coles import TeamRatings  # noqa: E402

OUT = ROOT / "apps" / "web" / "lib" / "api" / "mocks" / "recorded"

SEASON = "2026-27"
MODEL_RUN_ID = 57
RESETS_AT = "2026-10-16T00:00:00Z"
CONVERSATION_ID = "7d2f0a3c-5b1e-4c8a-9a47-0e6f3b21c5d8"

# name: (code, short name, attack, defense). Defense is how leaky the side is, so lower is better.
CLUBS: dict[str, tuple[str, str, float, float]] = {
    "1.FC Köln": ("KOE", "Köln", -0.05, 0.12),
    "1.FC Union Berlin": ("FCU", "Union Berlin", -0.18, -0.05),
    "1.FSV Mainz 05": ("M05", "Mainz", -0.05, -0.05),
    "Bayer 04 Leverkusen": ("B04", "Leverkusen", 0.30, -0.20),
    "Bayern Munich": ("FCB", "Bayern", 0.55, -0.40),
    "Borussia Dortmund": ("BVB", "Dortmund", 0.35, -0.15),
    "Borussia Mönchengladbach": ("BMG", "Gladbach", -0.05, 0.10),
    "Eintracht Frankfurt": ("SGE", "Frankfurt", 0.12, 0.02),
    "FC Augsburg": ("FCA", "Augsburg", -0.12, 0.05),
    "FC Schalke 04": ("S04", "Schalke", -0.18, 0.20),
    "Hamburger SV": ("HSV", "Hamburg", -0.12, 0.12),
    "RB Leipzig": ("RBL", "Leipzig", 0.25, -0.15),
    "SC Freiburg": ("SCF", "Freiburg", -0.02, -0.08),
    "SC Paderborn 07": ("SCP", "Paderborn", -0.28, 0.22),
    "SV 07 Elversberg": ("SVE", "Elversberg", -0.30, 0.25),
    "SV Werder Bremen": ("SVW", "Bremen", -0.08, 0.08),
    "TSG 1899 Hoffenheim": ("TSG", "Hoffenheim", 0.10, 0.08),
    "VfB Stuttgart": ("VFB", "Stuttgart", 0.15, -0.02),
}

# (fixture id, kickoff UTC, home, away) for one illustrative matchday.
MATCHDAY = 8
SCHEDULE = [
    (801, "2026-10-16T18:30:00Z", "Eintracht Frankfurt", "1.FC Köln"),
    (802, "2026-10-17T13:30:00Z", "Bayern Munich", "1.FSV Mainz 05"),
    (803, "2026-10-17T13:30:00Z", "Borussia Dortmund", "TSG 1899 Hoffenheim"),
    (804, "2026-10-17T13:30:00Z", "Bayer 04 Leverkusen", "FC Augsburg"),
    (805, "2026-10-17T13:30:00Z", "VfB Stuttgart", "Borussia Mönchengladbach"),
    (806, "2026-10-17T13:30:00Z", "FC Schalke 04", "SV 07 Elversberg"),
    (807, "2026-10-17T16:30:00Z", "RB Leipzig", "SC Freiburg"),
    (808, "2026-10-18T13:30:00Z", "SV Werder Bremen", "Hamburger SV"),
    (809, "2026-10-18T15:30:00Z", "1.FC Union Berlin", "SC Paderborn 07"),
]


def build_ratings() -> TeamRatings:
    names = tuple(sorted(CLUBS))
    attack = np.array([CLUBS[n][2] for n in names])
    defense = np.array([CLUBS[n][3] for n in names])
    return TeamRatings(
        teams=names,
        attack=attack - attack.mean(),
        defense=defense - defense.mean(),
        home_adv=0.28,
        rho=-0.1,
        log_likelihood=0.0,
    )


RATINGS = build_ratings()
TEAM_IDS = {name: index + 1 for index, name in enumerate(sorted(CLUBS))}


def team_json(name: str) -> dict[str, Any]:
    code, short_name, _, _ = CLUBS[name]
    return {
        "id": TEAM_IDS[name],
        "name": name,
        "short_name": short_name,
        "code": code,
        "crest": f"/crests/{code}.svg",
    }


def markets_json(home: str, away: str) -> dict[str, Any]:
    markets = RATINGS.predict(home, away)
    grid = [[round(p, 6) for p in row] for row in markets.score_grid]
    return {**markets_to_dict(markets), "score_grid": grid}


def fixture_cards() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    cards, details = [], {}
    for fixture_id, kickoff, home, away in SCHEDULE:
        markets = markets_json(home, away)
        keys = ("p_home", "p_draw", "p_away", "exp_home_goals", "exp_away_goals")
        card = {
            "id": fixture_id,
            "season": SEASON,
            "matchday": MATCHDAY,
            "kickoff_utc": kickoff,
            "home": team_json(home),
            "away": team_json(away),
            "base": {key: markets[key] for key in keys},
            "model_run_id": MODEL_RUN_ID,
        }
        cards.append(card)
        details[str(fixture_id)] = {**card, "markets": markets}
    return cards, details


def form(team: str, results: list[tuple[str, str, str, int, int]]) -> TeamForm:
    """Past results as (day, opponent, venue, goals for, goals against), newest first."""
    matches = tuple(
        FormMatch(
            date=date.fromisoformat(day),
            opponent=opponent,
            venue=venue,
            goals_for=goals_for,
            goals_against=goals_against,
            result="W" if goals_for > goals_against else "L" if goals_for < goals_against else "D",
        )
        for day, opponent, venue, goals_for, goals_against in results
    )
    wins = sum(m.result == "W" for m in matches)
    draws = sum(m.result == "D" for m in matches)
    return TeamForm(
        team=team,
        played=len(matches),
        wins=wins,
        draws=draws,
        losses=len(matches) - wins - draws,
        points=3 * wins + draws,
        goals_for=sum(m.goals_for for m in matches),
        goals_against=sum(m.goals_against for m in matches),
        matches=matches,
    )


FORMS = {
    "Bayern Munich": form(
        "Bayern Munich",
        [
            ("2026-10-04", "Eintracht Frankfurt", "H", 3, 1),
            ("2026-09-27", "SC Freiburg", "A", 2, 2),
            ("2026-09-20", "VfB Stuttgart", "H", 4, 0),
            ("2026-09-13", "Hamburger SV", "A", 3, 1),
            ("2026-09-06", "RB Leipzig", "H", 2, 1),
        ],
    ),
    "1.FSV Mainz 05": form(
        "1.FSV Mainz 05",
        [
            ("2026-10-03", "FC Augsburg", "H", 1, 1),
            ("2026-09-26", "Hamburger SV", "A", 0, 2),
            ("2026-09-19", "SC Paderborn 07", "H", 2, 0),
            ("2026-09-12", "Bayer 04 Leverkusen", "A", 1, 3),
            ("2026-09-05", "1.FC Köln", "H", 1, 0),
        ],
    ),
}

UPCOMING = {
    "Bayern Munich": [
        UpcomingFixture(
            kickoff_utc=datetime(2026, 10, 17, 13, 30),
            matchday=8,
            season=SEASON,
            home="Bayern Munich",
            away="1.FSV Mainz 05",
        ),
        UpcomingFixture(
            kickoff_utc=datetime(2026, 10, 24, 16, 30),
            matchday=9,
            season=SEASON,
            home="Borussia Dortmund",
            away="Bayern Munich",
        ),
    ]
}


def forecast(team: str, target: date) -> WeatherReport | None:
    if team != "Bayern Munich":
        return None
    return WeatherReport(
        team=team, city="Munich", date=target, temperature_c=11.4, wind_kmh=23.8, precip_mm=0.2
    )


class MockService(PredictionService):
    """The real engine, with the three database-backed lookups answered from fixed data."""

    def team_form(self, team: str, *, n: int = 5) -> TeamForm:
        return FORMS[team]

    def upcoming_fixtures(
        self, *, team: str | None = None, n: int = 9
    ) -> tuple[UpcomingFixture, ...]:
        return tuple(UPCOMING[team or "Bayern Munich"][:n])


def make_service() -> MockService:
    return MockService(RATINGS, as_of_date=date(2026, 10, 15), weather_provider=forecast)


def pct(value: float) -> str:
    return f"{round(value * 100)}%"


def summarize(name: str, tool_input: dict[str, Any], payload: dict[str, Any], ok: bool) -> str:
    if not ok:
        if payload.get("error") == "unknown team":
            return f"No ratings for {payload['team']}"
        return str(payload.get("error", "The tool call failed."))
    if name == "predict_match":
        home, away = tool_input["home"], tool_input["away"]
        return (
            f"{CLUBS[home][1]} {pct(payload['p_home'])}, draw {pct(payload['p_draw'])}, "
            f"{CLUBS[away][1]} {pct(payload['p_away'])}"
        )
    if name == "predict_match_with_context":
        count = len(payload["applied_adjustments"])
        before, after = payload["baseline"]["p_home"], payload["adjusted"]["p_home"]
        return (
            f"Home win {pct(before)} to {pct(after)} "
            f"with {count} adjustment{'s' if count != 1 else ''}"
        )
    if name == "get_team_form":
        return (
            f"{CLUBS[payload['team']][1]} {payload['record']} in the last {payload['played']}, "
            f"{payload['goals_for']} scored and {payload['goals_against']} conceded"
        )
    if name == "lookup_player":
        return f"{payload['name']}, {payload['role']}, {payload['importance']} importance"
    if name == "get_weather":
        return (
            f"{payload['city']}: {payload['temperature_c']:.0f} C, wind "
            f"{payload['wind_kmh']:.0f} km/h, {payload['precip_mm']} mm rain"
        )
    if name == "get_upcoming_fixtures":
        first = payload["fixtures"][0]
        return f"{len(payload['fixtures'])} fixtures, next {first['home']} v {first['away']}"
    return "Done"


def tool_use(call_id: str, tool: str, /, **tool_input: Any) -> FakeToolUseBlock:
    return FakeToolUseBlock(id=call_id, name=tool, input=tool_input)


def turn(*blocks: FakeToolUseBlock) -> FakeResponse:
    return FakeResponse(content=list(blocks), stop_reason="tool_use")


def record_stream(
    query: str,
    responses: list[FakeResponse],
    *,
    prediction_id: int,
    quota_used: int,
    quota_limit: int = 3,
    fail_after_tools: bool = False,
) -> list[dict[str, Any]]:
    service = make_service()
    frames: list[dict[str, Any]] = [
        {"event": "conversation", "data": {"id": CONVERSATION_ID, "title": query[:60].strip()}},
        {
            "event": "quota",
            "data": {"used": quota_used, "limit": quota_limit, "resets_at": RESETS_AT},
        },
    ]
    pending_input: dict[str, Any] = {}
    events: Iterator[AgentEvent] = run_agent_events(
        query, service, client=ScriptedClient(responses), model="recorded"
    )
    for event in events:
        if event.type == "tool_call":
            pending_input = dict(event.data["input"])
            stage = {"type": "tool_call", "name": event.data["name"], "input": pending_input}
            frames.append({"event": "stage", "data": stage})
        elif event.type == "tool_result":
            ok = bool(event.data["ok"])
            summary = summarize(event.data["name"], pending_input, event.data["payload"], ok)
            stage = {
                "type": "tool_result",
                "name": event.data["name"],
                "ok": ok,
                "summary": summary,
            }
            frames.append({"event": "stage", "data": stage})
        elif event.result is not None:
            if fail_after_tools:
                frames.append(
                    {
                        "event": "error",
                        "data": {
                            "code": "agent_failed",
                            "message": "The prediction could not be completed. Try again.",
                        },
                    }
                )
            else:
                response = build_response(event.result, event.result.record, prediction_id)
                frames.append({"event": "result", "data": response.model_dump(mode="json")})
    return frames


def adjusted_home_pct(home: str, away: str, adjustments: list[Adjustment]) -> tuple[str, str]:
    probe = make_service()
    baseline = probe.predict_match(home, away)
    adjusted = probe.predict_with_context(home, away, adjustments)
    return pct(baseline.p_home), pct(adjusted.p_home)


def happy_stream() -> list[dict[str, Any]]:
    home, away = "Borussia Dortmund", "TSG 1899 Hoffenheim"
    adjustments = [
        {
            "factor": "player_out",
            "team": "home",
            "target": "home_attack",
            "magnitude_xg": -0.35,
            "confidence": "high",
            "rationale": "First-choice striker Guirassy is out.",
        }
    ]
    before, after = adjusted_home_pct(home, away, [Adjustment(**a) for a in adjustments])
    text = (
        f"The base model has Dortmund at {before} to beat Hoffenheim. Guirassy is their main "
        "goal source and a penalty taker, so I took 0.35 expected goals off the Dortmund "
        f"attack. That moves the home win to {after}, with the draw and away win taking the "
        "difference. The rest of the squad is unchanged."
    )
    responses = [
        turn(tool_use("t1", "predict_match", home=home, away=away)),
        turn(tool_use("t2", "lookup_player", name="Serhou Guirassy")),
        turn(
            tool_use(
                "t3", "predict_match_with_context", home=home, away=away, adjustments=adjustments
            )
        ),
        FakeResponse(content=[FakeTextBlock(text)], stop_reason="end_turn"),
    ]
    query = "Guirassy is out for Dortmund, how does that change Dortmund v Hoffenheim?"
    return record_stream(query, responses, prediction_id=1842, quota_used=1)


def tool_heavy_stream() -> list[dict[str, Any]]:
    home, away = "Bayern Munich", "1.FSV Mainz 05"
    adjustments = [
        {
            "factor": "player_out",
            "team": "home",
            "target": "home_attack",
            "magnitude_xg": -0.3,
            "confidence": "med",
            "rationale": "Kane is doubtful; discounted rather than ruled out.",
        },
        {
            "factor": "congestion",
            "team": "away",
            "target": "away_attack",
            "magnitude_xg": -0.1,
            "confidence": "low",
            "rationale": "Mainz are expected to rotate after a midweek game.",
        },
    ]
    before, after = adjusted_home_pct(home, away, [Adjustment(**a) for a in adjustments])
    text = (
        f"Baseline has Bayern at {before}. Kane is only doubtful, so I applied a partial "
        "0.30 cut to the Bayern attack, and a small 0.10 cut to Mainz for likely rotation. "
        f"Munich shows 24 km/h wind and almost no rain, which is not enough to move scoring, "
        f"so I left weather out. Adjusted home win: {after}."
    )
    responses = [
        turn(
            tool_use("t1", "get_upcoming_fixtures", team=home, n=2),
            tool_use("t2", "predict_match", home=home, away=away),
        ),
        turn(
            tool_use("t3", "get_team_form", team=home),
            tool_use("t4", "get_team_form", team=away),
            tool_use("t5", "lookup_player", name="Harry Kane"),
        ),
        turn(tool_use("t6", "get_weather", team=home, date="2026-10-17")),
        turn(
            tool_use(
                "t7", "predict_match_with_context", home=home, away=away, adjustments=adjustments
            )
        ),
        FakeResponse(content=[FakeTextBlock(text)], stop_reason="end_turn"),
    ]
    query = "Kane is doubtful and Mainz may rotate, what does that do to Bayern v Mainz?"
    return record_stream(query, responses, prediction_id=1843, quota_used=2)


def error_stream() -> list[dict[str, Any]]:
    responses = [
        turn(tool_use("t1", "predict_match", home="Bayern Munich", away="Real Madrid")),
        FakeResponse(content=[FakeTextBlock("")], stop_reason="end_turn"),
    ]
    return record_stream(
        "Bayern against Real Madrid tonight?",
        responses,
        prediction_id=0,
        quota_used=2,
        fail_after_tools=True,
    )


def last_chat_stream() -> list[dict[str, Any]]:
    frames = happy_stream()
    frames[1]["data"]["used"] = frames[1]["data"]["limit"]
    return frames


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    cards, details = fixture_cards()
    write(OUT / "teams.json", [team_json(name) for name in sorted(CLUBS)])
    write(OUT / "fixtures.json", {"cards": cards, "details": details})
    write(OUT / "streams" / "happy.json", happy_stream())
    write(OUT / "streams" / "tool-heavy.json", tool_heavy_stream())
    write(OUT / "streams" / "error.json", error_stream())
    write(OUT / "streams" / "last-chat.json", last_chat_stream())


if __name__ == "__main__":
    main()
