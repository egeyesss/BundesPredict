"""Recorded-transcript tests for the agent loop (no live API)."""

from __future__ import annotations

import numpy as np

from bundespredict.agent.loop import run_agent
from bundespredict.agent.service import PredictionService
from bundespredict.agent.tools import TOOL_SPECS
from bundespredict.model.dixon_coles import TeamRatings

from .fakes import ScriptedClient, transcript_full, transcript_refusal

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


def test_full_run_applies_bounded_adjustments_and_explains() -> None:
    service = _service()
    client = ScriptedClient(transcript_full(HOME, AWAY))

    result = run_agent("striker out, windy", service, client=client)

    # Ended with a real explanation citing a delta.
    assert "47%" in result.explanation
    # The adjustment path ran: baseline + adjusted both recorded.
    assert result.record is not None
    assert result.record.adjusted is not None
    assert len(result.record.adjustments) == 2
    # Adjusted home win is below baseline (striker out + wind).
    assert result.record.adjusted.p_home < result.record.baseline.p_home


def test_loop_passes_tools_and_system_prompt() -> None:
    service = _service()
    client = ScriptedClient(transcript_full(HOME, AWAY))
    run_agent("striker out, windy", service, client=client)

    first_call = client.messages.calls[0]
    assert first_call["tools"] is TOOL_SPECS
    # System prompt names the canonical teams the model may use.
    assert HOME in first_call["system"]
    assert AWAY in first_call["system"]


def test_arguments_are_bounded_by_the_schema() -> None:
    # Every adjustment the transcript sent validates and sits inside the clamp;
    # the loop never lets an unbounded raw number through to the engine untyped.
    service = _service()
    client = ScriptedClient(transcript_full(HOME, AWAY))
    result = run_agent("striker out, windy", service, client=client)
    assert result.record is not None
    for adj in result.record.adjustments:
        assert abs(adj.magnitude_xg) <= 0.6


def test_refusal_path_leaves_baseline_unadjusted() -> None:
    service = _service()
    client = ScriptedClient(transcript_refusal(HOME, AWAY))

    result = run_agent("they have bad vibes", service, client=client)

    # Baseline was computed, but nothing was adjusted.
    assert result.record is not None
    assert result.record.adjusted is None
    assert len(result.record.adjustments) == 0
    assert "quantify" in result.explanation


def test_stops_at_max_turns() -> None:
    # A transcript that never stops calling tools must terminate at the ceiling
    # rather than loop forever.
    service = _service()
    loop_forever = transcript_full(HOME, AWAY)[:1] * 20  # always returns tool_use
    client = ScriptedClient(loop_forever)
    result = run_agent("x", service, client=client, max_turns=3)
    assert len(client.messages.calls) == 3
    assert isinstance(result.explanation, str)
