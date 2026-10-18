"""A scripted stand-in for the Anthropic client and recorded transcripts.

The loop only ever reads ``response.content`` / ``response.stop_reason`` and, on
each block, ``type`` plus (``id``/``name``/``input``) or ``text``. These light
fakes provide exactly that surface, so the loop can be exercised end to end with
no network and no API key. The transcript builders below are hand-authored to
mirror real tool-call sequences — the "cassettes" the loop is tested against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from bundespredict.data.fixtures import UpcomingFixture
from bundespredict.data.form import TeamForm
from bundespredict.data.players import DbPlayer, PlayerRow, pick_player
from bundespredict.data.results import ResultRow


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    content: list[Any]
    stop_reason: str
    usage: FakeUsage | None = None


class _ScriptedMessages:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if not self._responses:  # pragma: no cover - guards a misbuilt transcript
            raise AssertionError("scripted client ran out of responses")
        return self._responses.pop(0)


class ScriptedClient:
    """Satisfies the loop's ``LLMClient`` protocol with a fixed response script."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.messages = _ScriptedMessages(responses)


def transcript_full(home: str, away: str) -> list[FakeResponse]:
    """Baseline -> ground a player -> apply two adjustments -> explain.

    Models a query like "predict {home} vs {away}, their striker is out and it's
    going to be windy".
    """
    return [
        FakeResponse(
            content=[
                FakeToolUseBlock(id="t1", name="predict_match", input={"home": home, "away": away})
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[
                FakeToolUseBlock(id="t2", name="lookup_player", input={"name": "Serhou Guirassy"})
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[
                FakeToolUseBlock(
                    id="t3",
                    name="predict_match_with_context",
                    input={
                        "home": home,
                        "away": away,
                        "adjustments": [
                            {
                                "factor": "player_out",
                                "team": "home",
                                "target": "home_attack",
                                "magnitude_xg": -0.35,
                                "confidence": "high",
                                "rationale": "first-choice striker Guirassy out",
                            },
                            {
                                "factor": "weather_wind",
                                "team": "away",
                                "target": "away_attack",
                                "magnitude_xg": -0.1,
                                "confidence": "low",
                                "rationale": "strong wind trims both attacks",
                            },
                        ],
                    },
                )
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[
                FakeTextBlock(
                    "Baseline had the home side around 55%. Removing Guirassy cut their "
                    "expected goals and the wind trimmed the away attack, so the adjusted "
                    "home win drops to about 47%."
                )
            ],
            stop_reason="end_turn",
        ),
    ]


def transcript_refusal(home: str, away: str) -> list[FakeResponse]:
    """Baseline, then decline to adjust on un-quantifiable context."""
    return [
        FakeResponse(
            content=[
                FakeToolUseBlock(id="t1", name="predict_match", input={"home": home, "away": away})
            ],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[
                FakeTextBlock(
                    "You mentioned the home side has 'bad vibes', which isn't something I "
                    "can quantify, so I've left the model untouched. Baseline: home ~55%, "
                    "draw ~25%, away ~20%."
                )
            ],
            stop_reason="end_turn",
        ),
    ]


@dataclass
class StaticPorts:
    """Agent data ports over lists held in memory, with the same contracts as the Django ones."""

    results: tuple[ResultRow, ...] = ()
    fixtures: tuple[UpcomingFixture, ...] = ()
    player_rows: list[PlayerRow] = field(default_factory=list)
    forms: dict[str, TeamForm] = field(default_factory=dict)

    def team_form(self, team: str, *, as_of_date: date | None, n: int) -> TeamForm:
        if team not in self.forms:
            raise ValueError(f"unknown team: {team!r}")
        return self.forms[team]

    def latest_result_date(self) -> date | None:
        return max((r.date for r in self.results), default=None)

    def recent_results(self, *, as_of_date: date | None, n: int) -> tuple[ResultRow, ...]:
        eligible = [r for r in self.results if as_of_date is None or r.date < as_of_date]
        return tuple(sorted(eligible, key=lambda r: r.date, reverse=True)[:n])

    def find_player(self, query: str) -> DbPlayer | None:
        return pick_player(self.player_rows, query)

    def upcoming_fixtures(
        self, *, team: str | None, on_or_after: date, n: int
    ) -> tuple[UpcomingFixture, ...]:
        known = {name for f in self.fixtures for name in (f.home, f.away)}
        if team is not None and team not in known:
            raise ValueError(f"unknown team: {team!r}")
        upcoming = [
            f
            for f in self.fixtures
            if f.kickoff_utc >= datetime.combine(on_or_after, datetime.min.time())
            and (team is None or team in (f.home, f.away))
        ]
        return tuple(sorted(upcoming, key=lambda f: f.kickoff_utc)[:n])
