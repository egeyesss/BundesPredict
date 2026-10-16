"""Anthropic list prices per million tokens, for the models the agent can run on.

Prices checked against Anthropic's published model pricing on 2026-10-16. The agent sends no
`cache_control`, so cache read and write tokens never appear and only the plain input and output
rates are needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)

MILLION = Decimal(1_000_000)
COST_PRECISION = Decimal("0.000001")


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal


PRICES: dict[str, ModelPrice] = {
    "claude-haiku-4-5-20251001": ModelPrice(Decimal(1), Decimal(5)),
    "claude-haiku-4-5": ModelPrice(Decimal(1), Decimal(5)),
    "claude-sonnet-4-6": ModelPrice(Decimal(3), Decimal(15)),
    "claude-sonnet-5": ModelPrice(Decimal(2), Decimal(10)),
    "claude-sonnet-5-5": ModelPrice(Decimal(2), Decimal(10)),
    "claude-opus-5": ModelPrice(Decimal(5), Decimal(25)),
    "claude-opus-5-5": ModelPrice(Decimal(4), Decimal(20)),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Dollars for one run, to the micro-dollar; zero (and a log line) for an unpriced model."""
    price = PRICES.get(model)
    if price is None:
        logger.warning("no price for model %r, recording a cost of zero", model)
        return Decimal(0)
    total = (
        price.input_per_million * input_tokens + price.output_per_million * output_tokens
    ) / MILLION
    return total.quantize(COST_PRECISION)
