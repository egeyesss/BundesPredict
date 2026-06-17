"""Optional live smoke test against the real Anthropic API.

Skipped by default — it costs money and needs a key, so it never runs in CI.
Enable it for a manual check with::

    RUN_LIVE_AGENT=1 ANTHROPIC_API_KEY=sk-ant-... pytest tests/agent/test_live_smoke.py

It exercises the real tool-calling loop end to end on a synthetic two-team model,
asserting only that the agent produced a prediction and some explanation — not
any specific magnitude (those aren't deterministic).
"""

from __future__ import annotations

import os
from typing import cast

import numpy as np
import pytest

from bundespredict.agent.loop import DEV_MODEL, LLMClient, run_agent
from bundespredict.agent.service import PredictionService
from bundespredict.model.dixon_coles import TeamRatings

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_AGENT"),
    reason="set RUN_LIVE_AGENT=1 (and ANTHROPIC_API_KEY) to run the live smoke test",
)


def test_live_agent_produces_a_prediction() -> None:
    import anthropic

    ratings = TeamRatings(
        teams=("Borussia Dortmund", "RB Leipzig"),
        attack=np.array([0.4, -0.4]),
        defense=np.array([-0.2, 0.2]),
        home_adv=0.3,
        rho=-0.12,
        log_likelihood=0.0,
    )
    service = PredictionService(ratings)
    # The real client satisfies the loop's minimal LLMClient surface at runtime;
    # its precise overloaded type doesn't structurally match the Protocol, so cast.
    client = cast(LLMClient, anthropic.Anthropic())

    result = run_agent(
        "Predict Borussia Dortmund vs RB Leipzig. Their first-choice striker is out "
        "and it's going to be very windy.",
        service,
        client=client,
        model=DEV_MODEL,
    )

    assert result.record is not None
    assert result.explanation
