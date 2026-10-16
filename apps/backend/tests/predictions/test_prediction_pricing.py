"""Dollar cost of a run, from the token counts and the model's list price."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bundespredict.agent.loop import DEV_MODEL, PROD_MODEL
from predictions import pricing


def test_both_models_the_agent_runs_on_are_priced() -> None:
    assert DEV_MODEL in pricing.PRICES
    assert PROD_MODEL in pricing.PRICES


def test_haiku_costs_one_dollar_in_and_five_out_per_million_tokens() -> None:
    assert pricing.cost_usd(DEV_MODEL, 1_000_000, 1_000_000) == Decimal("6.000000")


def test_sonnet_costs_three_dollars_in_and_fifteen_out_per_million_tokens() -> None:
    assert pricing.cost_usd(PROD_MODEL, 1_000_000, 1_000_000) == Decimal("18.000000")


def test_small_runs_keep_micro_dollar_precision() -> None:
    assert pricing.cost_usd(DEV_MODEL, 4000, 800) == Decimal("0.008000")


def test_an_unpriced_model_costs_zero_and_is_logged(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Alembic's fileConfig in an earlier test disables pre-existing loggers for the session.
    monkeypatch.setattr(pricing.logger, "disabled", False)

    cost = pricing.cost_usd("claude-from-the-future", 1000, 1000)

    assert cost == Decimal("0")
    assert "claude-from-the-future" in caplog.text
