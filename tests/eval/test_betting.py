"""Tests for the value-bet simulation and CLV."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.eval.betting import value_bet_sim


def test_no_bet_when_edge_below_margin() -> None:
    model = np.array([[0.50, 0.30, 0.20]])
    market = np.array([[0.48, 0.30, 0.22]])  # max edge 0.02 < margin
    odds = np.array([[2.0, 3.3, 4.0]])
    out = np.array([0], dtype=np.intp)
    res = value_bet_sim(model, market, out, odds, odds, margin=0.05)
    assert res.n_bets == 0
    assert res.roi == 0.0


def test_winning_value_bet_pays_out() -> None:
    # Edge on home is 0.10 > margin; bet at 2.5 and home wins -> +1.5 on 1 staked.
    model = np.array([[0.60, 0.25, 0.15]])
    market = np.array([[0.50, 0.30, 0.20]])
    bet_odds = np.array([[2.5, 3.3, 4.0]])
    close_odds = np.array([[2.2, 3.3, 4.0]])
    out = np.array([0], dtype=np.intp)
    res = value_bet_sim(model, market, out, bet_odds, close_odds, margin=0.05)
    assert res.n_bets == 1
    assert res.n_wins == 1
    assert res.profit == pytest.approx(1.5)
    assert res.roi == pytest.approx(1.5)


def test_losing_value_bet_loses_stake() -> None:
    model = np.array([[0.60, 0.25, 0.15]])
    market = np.array([[0.50, 0.30, 0.20]])
    bet_odds = np.array([[2.5, 3.3, 4.0]])
    out = np.array([2], dtype=np.intp)  # away wins, our home bet loses
    res = value_bet_sim(model, market, out, bet_odds, bet_odds, margin=0.05)
    assert res.n_bets == 1
    assert res.n_wins == 0
    assert res.profit == pytest.approx(-1.0)
    assert res.roi == pytest.approx(-1.0)


def test_clv_measures_beating_the_close() -> None:
    # Bet home at 2.5, close is 2.2: we beat the close, CLV% = 2.5/2.2 - 1.
    model = np.array([[0.60, 0.25, 0.15]])
    market = np.array([[0.50, 0.30, 0.20]])
    bet_odds = np.array([[2.5, 3.3, 4.0]])
    close_odds = np.array([[2.2, 3.3, 4.0]])
    out = np.array([0], dtype=np.intp)
    res = value_bet_sim(model, market, out, bet_odds, close_odds, margin=0.05)
    assert res.beat_close_rate == pytest.approx(1.0)
    assert res.mean_clv_pct == pytest.approx(2.5 / 2.2 - 1.0)


def test_multiple_outcomes_can_each_be_bet() -> None:
    # Home and away both clear the margin in this row -> two independent bets.
    model = np.array([[0.45, 0.10, 0.45]])
    market = np.array([[0.35, 0.30, 0.35]])
    odds = np.array([[2.8, 3.3, 2.8]])
    out = np.array([0], dtype=np.intp)
    res = value_bet_sim(model, market, out, odds, odds, margin=0.05)
    assert res.n_bets == 2
    assert res.n_wins == 1  # home hits, away misses
