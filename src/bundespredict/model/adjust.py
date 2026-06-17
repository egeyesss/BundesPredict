"""Apply bounded expected-goals adjustments on top of a fitted model.

The agent layer turns natural-language context into typed adjustments; this is
the pure numeric path that those adjustments flow through to reach a new score
matrix. It stays in ``model/`` because the project rule is *given params +
adjustments -> distribution*, and it stays free of Pydantic/LLM types: the
boundary here is plain ``(target, magnitude)`` tuples and floats, so the whole
clamp/route/floor pipeline is trivially unit-testable without any agent code.

Three guarantees live here, all server-side regardless of what the LLM asked:

* **Clamping.** Every magnitude is capped to ``+/- MAGNITUDE_BOUND`` before it
  touches a lambda, so an absurd request (``+5.0``) can only ever move expected
  goals by ``+0.6``.
* **Routing.** A ``target`` maps to *which* side's expected goals it shifts.
  ``home_attack`` / ``away_defense`` / ``home_adv`` raise the home rate;
  ``away_attack`` / ``home_defense`` raise the away rate. The magnitude's sign
  carries direction (a striker out is ``home_attack`` with a negative value).
* **Lambda floor.** Adjustments add directly to lambda, so a weak team plus a
  big negative could drive lambda <= 0 and break the Poisson. After summing we
  floor each rate at ``LAMBDA_FLOOR``.

Disciplinary targets (``cards_rate`` / ``pen_rate``) are accepted and tracked
for audit but deliberately do **not** move expected goals: a strict referee must
never leak into the 1X2 result.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from bundespredict.model.dixon_coles import TeamRatings
from bundespredict.model.markets import DEFAULT_MAX_GOALS, Markets, markets

# A single adjustment can move expected goals by at most this much, in either
# direction. The agent's knowledge base lives well inside this; the cap is the
# hard backstop against the LLM (or a bug) asking for something absurd.
MAGNITUDE_BOUND = 0.6

# Adjustments add to lambda directly, so floor the result to keep the Poisson
# rate strictly positive (the score matrix needs lambda > 0).
LAMBDA_FLOOR = 0.05

# Which side's expected goals a target shifts. Defense targets cross over: a
# weaker home defense means the *away* side scores more, and vice versa.
_HOME_GOAL_TARGETS = frozenset({"home_attack", "away_defense", "home_adv"})
_AWAY_GOAL_TARGETS = frozenset({"away_attack", "home_defense"})
# Tracked for audit but never fed into the goal rates (see module docstring).
_DISCIPLINE_TARGETS = frozenset({"cards_rate", "pen_rate"})

GOAL_TARGETS = _HOME_GOAL_TARGETS | _AWAY_GOAL_TARGETS
ALL_TARGETS = GOAL_TARGETS | _DISCIPLINE_TARGETS


def clamp_magnitude(magnitude: float) -> float:
    """Cap a single adjustment magnitude to ``+/- MAGNITUDE_BOUND``."""
    return max(-MAGNITUDE_BOUND, min(MAGNITUDE_BOUND, magnitude))


@dataclass(frozen=True)
class GoalAdjustment:
    """Resolved per-side expected-goals deltas after clamping and routing.

    ``home_delta`` / ``away_delta`` are added to the home/away expected goals.
    ``discipline`` accumulates clamped cards/penalty magnitudes purely so the
    agent can report them; they have no effect on the goal distribution.
    """

    home_delta: float
    away_delta: float
    discipline: dict[str, float]


def resolve_goal_deltas(adjustments: Iterable[tuple[str, float]]) -> GoalAdjustment:
    """Clamp and route ``(target, magnitude)`` pairs into per-side goal deltas.

    Raises ``ValueError`` on an unknown target; every magnitude is clamped before
    it is summed, so the totals are bounded by the number of adjustments times
    ``MAGNITUDE_BOUND`` and nothing here trusts the caller's range.
    """
    home_delta = 0.0
    away_delta = 0.0
    discipline: dict[str, float] = {}
    for target, magnitude in adjustments:
        if target not in ALL_TARGETS:
            raise ValueError(f"unknown adjustment target: {target!r}")
        m = clamp_magnitude(magnitude)
        if target in _HOME_GOAL_TARGETS:
            home_delta += m
        elif target in _AWAY_GOAL_TARGETS:
            away_delta += m
        else:
            discipline[target] = discipline.get(target, 0.0) + m
    return GoalAdjustment(home_delta=home_delta, away_delta=away_delta, discipline=discipline)


def adjusted_expected_goals(
    base_home: float, base_away: float, delta: GoalAdjustment
) -> tuple[float, float]:
    """Apply the resolved deltas to base expected goals, floored at the minimum.

    The floor is what keeps a large negative adjustment from driving a low-rate
    team's lambda to zero or below.
    """
    lambda_home = max(base_home + delta.home_delta, LAMBDA_FLOOR)
    mu_away = max(base_away + delta.away_delta, LAMBDA_FLOOR)
    return lambda_home, mu_away


def predict_adjusted(
    ratings: TeamRatings,
    home: str,
    away: str,
    adjustments: Iterable[tuple[str, float]],
    *,
    max_goals: int = DEFAULT_MAX_GOALS,
) -> Markets:
    """Full market distribution for a fixture with adjustments applied.

    Same shape as :meth:`TeamRatings.predict`, but the base expected goals are
    nudged by the (clamped, routed, floored) adjustments before the score matrix
    is built. Passing an empty ``adjustments`` reproduces the baseline exactly.
    """
    base_home, base_away = ratings.expected_goals(home, away)
    delta = resolve_goal_deltas(adjustments)
    lambda_home, mu_away = adjusted_expected_goals(base_home, base_away, delta)
    return markets(lambda_home, mu_away, rho=ratings.rho, max_goals=max_goals)
