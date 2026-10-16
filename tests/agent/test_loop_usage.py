"""The loop reports the token usage of every LLM call it made."""

from __future__ import annotations

import numpy as np

from bundespredict.agent.loop import TokenUsage, run_agent
from bundespredict.agent.service import PredictionService
from bundespredict.model.dixon_coles import TeamRatings

from .fakes import (
    FakeResponse,
    FakeTextBlock,
    FakeToolUseBlock,
    FakeUsage,
    ScriptedClient,
)

HOME = "Borussia Dortmund"
AWAY = "RB Leipzig"


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


def _tool_call(usage: FakeUsage | None) -> FakeResponse:
    block = FakeToolUseBlock(id="t1", name="predict_match", input={"home": HOME, "away": AWAY})
    return FakeResponse(content=[block], stop_reason="tool_use", usage=usage)


def _answer(usage: FakeUsage | None) -> FakeResponse:
    return FakeResponse(content=[FakeTextBlock("Done.")], stop_reason="end_turn", usage=usage)


def test_usage_is_summed_over_every_llm_call() -> None:
    client = ScriptedClient([_tool_call(FakeUsage(900, 40)), _answer(FakeUsage(1100, 60))])

    result = run_agent("who wins", _service(), client=client)

    assert result.usage == TokenUsage(input_tokens=2000, output_tokens=100)


def test_a_response_without_a_usage_block_counts_as_zero() -> None:
    client = ScriptedClient([_tool_call(None), _answer(FakeUsage(10, 5))])

    result = run_agent("who wins", _service(), client=client)

    assert result.usage == TokenUsage(input_tokens=10, output_tokens=5)


def test_a_run_with_no_usage_at_all_reports_zero() -> None:
    result = run_agent("hi", _service(), client=ScriptedClient([_answer(None)]))

    assert result.usage == TokenUsage(input_tokens=0, output_tokens=0)
