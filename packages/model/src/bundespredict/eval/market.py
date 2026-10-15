"""Turn bookmaker 1X2 odds into a probability baseline.

Decimal odds imply a probability of ``1 / odds``, but a book builds in a margin
(the *overround* / *vig*): the three implied probabilities sum to more than 1, and
that excess is the book's edge. The de-vigged probabilities are the market's
honest opinion once the margin is stripped out — and they are the **strong
baseline** the model is measured against. Matching them is good; beating them is
hard, and saying so plainly is the whole point of the evaluation.

De-vigging here is the simple *proportional* normalization (divide by the sum).
It's the standard first cut; margin-aware methods (Shin, the power method) shave
the favourite-longshot bias a little but need assumptions this project doesn't
lean on yet. Pure and array-friendly: odds in, probabilities out, no I/O.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Odds columns are ordered [home, draw, away] to match metrics' class order.


def _as_odds_array(odds: NDArray[np.float64]) -> NDArray[np.float64]:
    arr = np.asarray(odds, dtype=np.float64)
    if arr.shape[-1] != 3:
        raise ValueError(f"odds last axis must be length 3 (H,D,A), got {arr.shape}")
    if np.any(arr <= 1.0):
        raise ValueError("decimal odds must be > 1.0")
    return arr


def implied_probs(odds: NDArray[np.float64]) -> NDArray[np.float64]:
    """Raw implied probabilities ``1 / odds`` — these still carry the overround."""
    return np.asarray(1.0 / _as_odds_array(odds), dtype=np.float64)


def overround(odds: NDArray[np.float64]) -> NDArray[np.float64]:
    """The book's margin: ``sum(1 / odds) - 1`` per match (0 = a fair book)."""
    return np.asarray(implied_probs(odds).sum(axis=-1) - 1.0, dtype=np.float64)


def devig(odds: NDArray[np.float64]) -> NDArray[np.float64]:
    """De-vigged 1X2 probabilities: implied, then normalized to sum to 1.

    Accepts a single ``(3,)`` triple or an ``(N, 3)`` batch; the result has the
    same shape and each row sums to 1. This is the market baseline fed straight
    into the same metrics as the model's predictions.
    """
    implied = implied_probs(odds)
    return np.asarray(implied / implied.sum(axis=-1, keepdims=True), dtype=np.float64)
