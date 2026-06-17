"""Tests for the Adjustment schema and the magnitude knowledge base."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from bundespredict.agent.adjustments import Adjustment, KBEntry, Target, load_kb
from bundespredict.model.adjust import ALL_TARGETS, MAGNITUDE_BOUND


def _valid(**overrides: object) -> Adjustment:
    base: dict[str, object] = {
        "factor": "player_out",
        "team": "home",
        "target": "home_attack",
        "magnitude_xg": -0.3,
        "confidence": "med",
        "rationale": "first-choice striker suspended",
    }
    base.update(overrides)
    return Adjustment(**base)  # type: ignore[arg-type]


# --- schema validation ----------------------------------------------------


def test_valid_adjustment_round_trips() -> None:
    adj = _valid()
    assert adj.as_delta() == ("home_attack", -0.3)
    assert not adj.is_disciplinary


def test_out_of_range_magnitude_is_kept_not_clamped() -> None:
    # The audit trail records what the LLM asked for; the engine clamps when it
    # applies. A +5.0 request is a valid object whose effect is bounded elsewhere.
    adj = _valid(magnitude_xg=5.0)
    assert adj.magnitude_xg == 5.0


def test_non_finite_magnitude_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(magnitude_xg=float("nan"))
    with pytest.raises(ValidationError):
        _valid(magnitude_xg=float("inf"))


def test_empty_rationale_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(rationale="   ")


def test_unknown_factor_or_target_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(factor="bad_vibes")
    with pytest.raises(ValidationError):
        _valid(target="midfield")


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        _valid(p_home=0.9)


def test_disciplinary_flag() -> None:
    assert _valid(factor="referee_cards", target="cards_rate", team=None).is_disciplinary
    assert _valid(factor="referee_penalty", target="pen_rate", team=None).is_disciplinary


# --- drift guard: schema targets must equal the engine's routing table ----


def test_schema_targets_match_engine_targets() -> None:
    schema_targets = set(get_args(Target))
    assert schema_targets == ALL_TARGETS


# --- knowledge base -------------------------------------------------------


def test_kb_loads_and_validates() -> None:
    entries = load_kb()
    assert len(entries) > 0
    assert all(isinstance(e, KBEntry) for e in entries)


def test_kb_entries_are_sourced() -> None:
    # Every range carries a source: a citation or the explicit "heuristic" label.
    for entry in load_kb():
        assert entry.source.strip(), f"{entry.name} has no source"


def test_kb_ranges_are_ordered_and_within_clamp() -> None:
    for entry in load_kb():
        assert entry.min_xg <= entry.max_xg, f"{entry.name} range inverted"
        assert abs(entry.min_xg) <= MAGNITUDE_BOUND
        assert abs(entry.max_xg) <= MAGNITUDE_BOUND


def test_kb_targets_are_valid_engine_targets() -> None:
    for entry in load_kb():
        assert entry.target in ALL_TARGETS
