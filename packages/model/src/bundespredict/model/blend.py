"""Blend model and market probabilities with a logarithmic opinion pool.

The market's de-vigged odds are a strong forecast in their own right, and the
model sees things the market prices in differently — so the pragmatic way to
close the RPS gap is to combine them rather than pretend one is strictly
better. The log opinion pool is the standard combiner for probability
forecasts::

    p_blend ∝ p_model^(1-w) · p_market^w

renormalized per match. It is a geometric average, so unlike a linear mixture
it stays sharp when both sources agree and hedges only where they disagree.
One parameter ``w ∈ [0, 1]`` sets the market's weight: ``w = 0`` returns the
model untouched, ``w = 1`` the market.

``w`` is a genuine hyperparameter and gets the same treatment xi did: chosen
by **walk-forward log-likelihood, never a single split** (one holdout window
right after a cutoff rewards whatever happened to work that month). There is
no fit step for a fixed ``w``, so each candidate is scored directly on the
rolling out-of-sample windows and the pooled per-match log-likelihood decides.

The blend is evaluation/serving output only. Agent adjustments keep applying
to the model's λ upstream — this module averages *probabilities* and nothing
here feeds back into the engine, so the "no tool accepts a probability"
contract is untouched. Pure: arrays in, arrays out, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

_EPS = 1e-12

# Candidate market weights. The endpoints are included on purpose: if the
# search runs to w=1 the model adds nothing over the market, and that is worth
# seeing plainly rather than hiding behind an interior-only grid.
DEFAULT_W_GRID: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def _validate_probs(probs: NDArray[np.float64], name: str) -> NDArray[np.float64]:
    arr = np.asarray(probs, dtype=np.float64)
    if arr.shape[-1] != 3:
        raise ValueError(f"{name} last axis must be length 3 (H,D,A), got {arr.shape}")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise ValueError(f"{name} must be probabilities in [0, 1]")
    return arr


def blend_probs(
    p_model: NDArray[np.float64],
    p_market: NDArray[np.float64],
    w: float,
) -> NDArray[np.float64]:
    """Log-opinion-pool blend of two 1X2 forecasts with market weight ``w``.

    Accepts a single ``(3,)`` triple or an ``(N, 3)`` batch (shapes must match);
    the result has the same shape and each row sums to 1. ``w = 0`` reproduces
    ``p_model`` exactly and ``w = 1`` reproduces ``p_market`` — the structural
    reductions the tests pin down.
    """
    if not 0.0 <= w <= 1.0:
        raise ValueError(f"w must be in [0, 1], got {w}")
    model = _validate_probs(p_model, "p_model")
    market = _validate_probs(p_market, "p_market")
    if model.shape != market.shape:
        raise ValueError(f"shape mismatch: p_model {model.shape} vs p_market {market.shape}")

    # Work in log space; the clip only guards true zeros (log(0)) and is far
    # below any probability the model or a de-vigged book actually emits.
    log_blend = (1.0 - w) * np.log(np.clip(model, _EPS, 1.0)) + w * np.log(
        np.clip(market, _EPS, 1.0)
    )
    log_blend -= log_blend.max(axis=-1, keepdims=True)  # stabilize before exp
    unnormalized = np.exp(log_blend)
    return np.asarray(unnormalized / unnormalized.sum(axis=-1, keepdims=True), dtype=np.float64)


@dataclass(frozen=True)
class BlendSelection:
    """Result of the walk-forward search: the winning weight and every candidate's score."""

    w: float
    holdout_log_likelihood: float  # mean per-fold LL of the winner, across all folds
    scores: tuple[tuple[float, float], ...]  # (w, mean walk-forward log-likelihood)


def select_blend_weight(
    p_model: NDArray[np.float64],
    p_market: NDArray[np.float64],
    outcomes: NDArray[np.intp],
    day_ordinal: NDArray[np.intp],
    *,
    n_folds: int = 6,
    fold_days: int = 120,
    w_grid: tuple[float, ...] = DEFAULT_W_GRID,
) -> BlendSelection:
    """Choose the market weight by mean walk-forward log-likelihood.

    Same shape as ``time_decay.select_xi``: rolling windows, each ``fold_days``
    wide, ``n_folds`` of them ending at the most recent match. A fixed ``w``
    has nothing to fit, so each candidate is scored directly per window (mean
    per-match log-likelihood) and the *fold means* are averaged — every period
    votes with equal weight, so one lucky dense month can't pick the weight the
    way a single train/holdout split would.

    The inputs must themselves be leakage-safe (the backtest's out-of-sample
    model probabilities and de-vigged *opening* odds — closing odds would leak
    late information into the thing we then claim beats the open).
    """
    model = _validate_probs(p_model, "p_model")
    market = _validate_probs(p_market, "p_market")
    if model.shape != market.shape or model.ndim != 2:
        raise ValueError("p_model and p_market must both be (N, 3) and aligned")
    n = model.shape[0]
    if outcomes.shape != (n,) or day_ordinal.shape != (n,):
        raise ValueError("outcomes and day_ordinal must align with the probability rows")
    if n == 0:
        raise ValueError("no matches to select the blend weight from")

    max_day = int(day_ordinal.max())
    fold_masks: list[NDArray[np.bool_]] = []
    for k in range(n_folds, 0, -1):
        end = max_day - (k - 1) * fold_days
        mask = (day_ordinal > end - fold_days) & (day_ordinal <= end)
        if mask.any():
            fold_masks.append(mask)
    if not fold_masks:
        raise ValueError("not enough history for the requested windows")

    scores: list[tuple[float, float]] = []
    for w in w_grid:
        fold_lls: list[float] = []
        for mask in fold_masks:
            blended = blend_probs(model[mask], market[mask], w)
            picked = blended[np.arange(int(mask.sum())), outcomes[mask]]
            fold_lls.append(float(np.mean(np.log(np.clip(picked, _EPS, 1.0)))))
        scores.append((w, float(np.mean(fold_lls))))

    best_w, best_ll = max(scores, key=lambda s: s[1])
    return BlendSelection(w=best_w, holdout_log_likelihood=best_ll, scores=tuple(scores))
