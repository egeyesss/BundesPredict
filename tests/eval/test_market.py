"""Tests for de-vigging bookmaker odds into a probability baseline."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.eval.market import devig, implied_probs, overround


def test_devigged_probs_sum_to_one() -> None:
    odds = np.array([2.0, 3.5, 4.0])
    probs = devig(odds)
    assert probs.sum() == pytest.approx(1.0)
    # Order preserved: shortest odds -> highest probability.
    assert probs[0] > probs[1] and probs[0] > probs[2]


def test_overround_is_positive_for_a_real_book() -> None:
    # A book quoting 1/odds that sum above 1 keeps the excess as margin.
    odds = np.array([2.0, 3.5, 4.0])
    assert overround(odds) > 0.0
    assert implied_probs(odds).sum() == pytest.approx(1.0 + overround(odds))


def test_fair_book_round_trips() -> None:
    # Odds of exactly 1/p for a fair (margin-free) book recover p unchanged.
    p = np.array([0.5, 0.3, 0.2])
    odds = 1.0 / p
    assert overround(odds) == pytest.approx(0.0)
    assert devig(odds) == pytest.approx(p)


def test_batch_shape_preserved() -> None:
    odds = np.array([[2.0, 3.5, 4.0], [1.5, 4.5, 6.0]])
    probs = devig(odds)
    assert probs.shape == (2, 3)
    assert probs.sum(axis=1) == pytest.approx([1.0, 1.0])


def test_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError, match="> 1.0"):
        devig(np.array([1.0, 3.0, 4.0]))
    with pytest.raises(ValueError, match="length 3"):
        devig(np.array([2.0, 3.0]))
