"""Flat-stake value betting and Closing Line Value.

The honest test of edge: only bet when the model's probability for an outcome
beats the de-vigged consensus by a margin (a real disagreement, not noise), stake
one unit at the bookmaker's price, and tally the return. Expect roughly
break-even-minus-vig — beating a sharp market is hard, and reporting that plainly
is the whole maturity flex here. Don't dress it up.

ROI answers "did this make money over the sample," which is mostly variance on a
few hundred bets. **Closing Line Value** answers the better question: did we
take prices the market later moved toward? Betting at the opening line and
measuring against the close, a positive CLV means we systematically got a better
price than the closing — the signal pros trust because it survives variance.
True CLV needs both the price we bet at and the closing price, which is exactly
why the closing odds are ingested alongside the opening line.

Pure: arrays in, a summary out. No DB, no plotting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class BettingResult:
    """Outcome of a flat-stake value-betting simulation."""

    n_bets: int
    total_staked: float
    profit: float
    roi: float  # profit / total_staked
    n_wins: int
    win_rate: float
    beat_close_rate: float  # share of bets whose price beat the closing line
    mean_clv_pct: float  # mean(opening_odds / closing_odds - 1) across bets


def value_bet_sim(
    model_probs: NDArray[np.float64],
    market_probs: NDArray[np.float64],
    outcomes: NDArray[np.intp],
    bet_odds: NDArray[np.float64],
    close_odds: NDArray[np.float64],
    *,
    margin: float = 0.05,
    stake: float = 1.0,
) -> BettingResult:
    """Bet every outcome where ``model_prob - market_prob > margin``.

    ``market_probs`` is the de-vigged consensus used to spot value; ``bet_odds``
    is the decimal price actually taken (the opening Bet365 line) and
    ``close_odds`` the closing line CLV is measured against. All are ``(N, 3)`` in
    ``[home, draw, away]`` order. Each qualifying cell is an independent one-unit
    bet.
    """
    for name, arr in (
        ("model_probs", model_probs),
        ("market_probs", market_probs),
        ("bet_odds", bet_odds),
        ("close_odds", close_odds),
    ):
        if arr.shape != model_probs.shape:
            raise ValueError(f"{name} shape {arr.shape} != {model_probs.shape}")

    edge = model_probs - market_probs
    bet_mask = edge > margin  # (N, 3) boolean

    hit = np.zeros_like(model_probs, dtype=bool)
    hit[np.arange(outcomes.shape[0]), outcomes] = True

    placed = bet_mask
    n_bets = int(placed.sum())
    if n_bets == 0:
        return BettingResult(0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0)

    won = placed & hit
    total_staked = n_bets * stake
    # Winners return (odds - 1) * stake; losers lose the stake. Sum the winners'
    # net and subtract the losers' stakes.
    profit = float((bet_odds[won] - 1.0).sum() * stake - (n_bets - int(won.sum())) * stake)

    open_p = bet_odds[placed]
    close_p = close_odds[placed]
    beat_close_rate = float(np.mean(open_p > close_p))
    mean_clv_pct = float(np.mean(open_p / close_p - 1.0))

    return BettingResult(
        n_bets=n_bets,
        total_staked=total_staked,
        profit=profit,
        roi=profit / total_staked,
        n_wins=int(won.sum()),
        win_rate=int(won.sum()) / n_bets,
        beat_close_rate=beat_close_rate,
        mean_clv_pct=mean_clv_pct,
    )
