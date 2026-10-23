"""A fixture the chat was opened from reaches the model as the subject of the conversation."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from bundespredict.agent.loop import run_agent
from bundespredict.agent.prompt import PinnedFixture, build_system_prompt
from bundespredict.agent.service import PredictionService
from bundespredict.model.dixon_coles import TeamRatings

from .fakes import FakeResponse, FakeTextBlock, ScriptedClient

HOME = "RB Leipzig"
AWAY = "Elversberg"
PINNED = PinnedFixture(
    fixture_id=412,
    home=HOME,
    away=AWAY,
    kickoff_utc=datetime(2026, 10, 24, 13, 30, tzinfo=UTC),
)


def _service() -> PredictionService:
    ratings = TeamRatings(
        teams=(HOME, AWAY),
        attack=np.array([0.4, -0.4]),
        defense=np.array([-0.2, 0.2]),
        home_adv=0.3,
        rho=-0.12,
        log_likelihood=0.0,
    )
    return PredictionService(ratings)


def test_the_pinned_fixture_is_named_in_the_system_prompt() -> None:
    prompt = build_system_prompt((HOME, AWAY), pinned_fixture=PINNED)

    assert "RB Leipzig v Elversberg" in prompt
    assert "2026-10-24" in prompt
    assert "412" in prompt


def test_no_pinned_fixture_leaves_the_prompt_unchanged() -> None:
    assert build_system_prompt((HOME, AWAY)) == build_system_prompt(
        (HOME, AWAY), pinned_fixture=None
    )


def test_the_system_prompt_sent_to_the_client_carries_the_pinned_fixture() -> None:
    client = ScriptedClient([FakeResponse([FakeTextBlock("ok")], "end_turn")])

    run_agent("Weather at kickoff is stormy", _service(), client=client, pinned_fixture=PINNED)

    system = client.messages.calls[0]["system"]
    assert "RB Leipzig v Elversberg" in system
