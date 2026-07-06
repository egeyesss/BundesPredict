"""Tests for the log-opinion-pool market blend."""

from __future__ import annotations

import numpy as np
import pytest

from bundespredict.model.blend import blend_probs, select_blend_weight

MODEL = np.array([[0.50, 0.30, 0.20], [0.20, 0.30, 0.50], [0.34, 0.33, 0.33]])
MARKET = np.array([[0.40, 0.30, 0.30], [0.25, 0.25, 0.50], [0.60, 0.25, 0.15]])


def test_w_zero_reduces_to_model() -> None:
    assert blend_probs(MODEL, MARKET, 0.0) == pytest.approx(MODEL)


def test_w_one_reduces_to_market() -> None:
    assert blend_probs(MODEL, MARKET, 1.0) == pytest.approx(MARKET)


def test_blend_is_valid_distribution() -> None:
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        blended = blend_probs(MODEL, MARKET, w)
        assert blended.shape == MODEL.shape
        assert np.all(blended >= 0.0)
        assert blended.sum(axis=-1) == pytest.approx(np.ones(len(MODEL)))


def test_single_triple_shape() -> None:
    blended = blend_probs(MODEL[0], MARKET[0], 0.5)
    assert blended.shape == (3,)
    assert blended.sum() == pytest.approx(1.0)


def test_agreement_passes_through() -> None:
    # When both sources agree the geometric pool must not hedge toward uniform.
    assert blend_probs(MODEL, MODEL, 0.5) == pytest.approx(MODEL)


def test_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match=r"w must be in \[0, 1\]"):
        blend_probs(MODEL, MARKET, 1.5)
    with pytest.raises(ValueError, match="last axis"):
        blend_probs(np.zeros((2, 2)), np.zeros((2, 2)), 0.5)
    with pytest.raises(ValueError, match="shape mismatch"):
        blend_probs(MODEL, MARKET[:2], 0.5)
    with pytest.raises(ValueError, match=r"in \[0, 1\]"):
        blend_probs(MODEL + 0.6, MARKET, 0.5)


def _synthetic_forecasts(
    n: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """True probs, a sharp/noisy model, outcomes drawn from the truth, day ordinals.

    The market *is* the true distribution; the model is the truth with doubled
    logits (overconfident) plus per-match noise. The best blend weight should
    therefore sit near the market end of the grid.
    """
    rng = np.random.default_rng(seed)
    logits = rng.normal(0.0, 0.5, size=(n, 3))
    true = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)

    noisy_logits = 2.0 * np.log(true) + rng.normal(0.0, 0.8, size=(n, 3))
    noisy_logits -= noisy_logits.max(axis=1, keepdims=True)
    model = np.exp(noisy_logits) / np.exp(noisy_logits).sum(axis=1, keepdims=True)

    outcomes = np.array([rng.choice(3, p=p) for p in true], dtype=np.intp)
    days = np.arange(n, dtype=np.intp)  # one match a day, ~2 years for n=720
    return true, model, outcomes, days


def test_selection_prefers_market_when_market_is_true() -> None:
    true, model, outcomes, days = _synthetic_forecasts(720, seed=11)
    sel = select_blend_weight(model, true, outcomes, days, fold_days=60)
    assert sel.w >= 0.7


def test_selection_prefers_model_when_model_is_true() -> None:
    true, market, outcomes, days = _synthetic_forecasts(720, seed=12)
    # Same setup mirrored: now the *model* argument is the true distribution.
    sel = select_blend_weight(true, market, outcomes, days, fold_days=60)
    assert sel.w <= 0.3


def test_selection_scores_cover_grid_and_winner_is_argmax() -> None:
    true, model, outcomes, days = _synthetic_forecasts(360, seed=13)
    sel = select_blend_weight(model, true, outcomes, days, fold_days=60)
    ws = [w for w, _ in sel.scores]
    assert ws == sorted(ws) and len(ws) == 11
    best_w, best_ll = max(sel.scores, key=lambda s: s[1])
    assert sel.w == best_w
    assert sel.holdout_log_likelihood == best_ll


def test_selection_rejects_misaligned_inputs() -> None:
    true, model, outcomes, days = _synthetic_forecasts(50, seed=14)
    with pytest.raises(ValueError, match="align"):
        select_blend_weight(model, true, outcomes[:-1], days)
    with pytest.raises(ValueError, match="no matches"):
        select_blend_weight(
            np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, dtype=np.intp), np.zeros(0, np.intp)
        )
