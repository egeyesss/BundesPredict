"""Dixon-Coles fit: hand-rolled weighted MLE over match results.

Each team carries an attack strength (alpha) and a defensive weakness (beta);
the home side gets a global advantage (gamma). Expected goals are log-linear::

    lambda_home = exp(alpha_home + beta_away + gamma)
    mu_away     = exp(alpha_away + beta_home)

Goals are independent Poisson with those means, plus the Dixon-Coles ``rho``
correction on the four low-score cells (see :mod:`bundespredict.model.markets`).
The tau correction breaks standard GLM fitting, so the weighted log-likelihood is
written out by hand and minimized with ``scipy.optimize.minimize``.

This module is pure: it takes plain integer-indexed arrays in and returns a
frozen ratings object. It never touches the database or the network — a loader
outside ``model/`` is responsible for turning rows into :class:`MatchData`.

Identifiability: attack and defense are each only defined up to an additive
constant, so we pin the gauge with **sum-to-zero** (``sum(alpha) = sum(beta) =
0``) enforced *by construction* — only ``n - 1`` of each are free parameters and
the last is set to minus their sum. That keeps the optimization non-degenerate
(no flat direction) without an explicit constraint.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.special import gammaln

from bundespredict.model.markets import DEFAULT_MAX_GOALS, Markets, markets

# Home advantage starts around exp(0.25) ~ 1.28x scoring; a sane optimizer seed.
_INIT_HOME_ADV = 0.25
_INIT_RHO = -0.1
# Keep rho where tau stays positive for realistic lambdas; brackets the -0.13 ref.
_RHO_BOUNDS = (-0.2, 0.2)


@dataclass(frozen=True)
class MatchData:
    """Integer-indexed match arrays handed to the fitter — the pure interface.

    ``teams`` lists team identifiers in index order; the ``*_idx`` arrays index
    into it. ``weights`` carries the time-decay weight per match (all ones means
    unweighted). A loader builds this from the database; the engine only sees
    arrays.
    """

    teams: tuple[str, ...]
    home_idx: NDArray[np.intp]
    away_idx: NDArray[np.intp]
    home_goals: NDArray[np.intp]
    away_goals: NDArray[np.intp]
    weights: NDArray[np.float64]

    @property
    def n_teams(self) -> int:
        return len(self.teams)


@dataclass(frozen=True)
class TeamRatings:
    """Fitted parameters: the engine's whole state. Immutable and serializable.

    ``attack`` and ``defense`` are in log space and each sum to zero. ``rho`` is
    the Dixon-Coles correction (0 means the fit was plain independent Poisson).
    """

    teams: tuple[str, ...]
    attack: NDArray[np.float64]
    defense: NDArray[np.float64]
    home_adv: float
    rho: float
    log_likelihood: float
    _index: dict[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Frozen dataclass: set the lookup map through object.__setattr__.
        object.__setattr__(self, "_index", {t: i for i, t in enumerate(self.teams)})

    def index(self, team: str) -> int:
        return self._index[team]

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        """Pre-match expected goals (lambda_home, mu_away) for a fixture."""
        h, a = self._index[home], self._index[away]
        lambda_home = float(np.exp(self.attack[h] + self.defense[a] + self.home_adv))
        mu_away = float(np.exp(self.attack[a] + self.defense[h]))
        return lambda_home, mu_away

    def predict(self, home: str, away: str, *, max_goals: int = DEFAULT_MAX_GOALS) -> Markets:
        """Full market distribution for a fixture, using this fit's ``rho``."""
        lambda_home, mu_away = self.expected_goals(home, away)
        return markets(lambda_home, mu_away, rho=self.rho, max_goals=max_goals)


def _log_tau(
    home_goals: NDArray[np.intp],
    away_goals: NDArray[np.intp],
    lam: NDArray[np.float64],
    mu: NDArray[np.float64],
    rho: float,
) -> NDArray[np.float64]:
    """Log of the Dixon-Coles tau correction, vectorized over matches.

    tau is 1 everywhere except the four low-score cells, so we start at ones and
    overwrite the masked entries. The ``maximum`` guard keeps ``log`` finite if
    the optimizer probes a rho that would drive tau non-positive (the rho bounds
    make this rare, but a single bad eval shouldn't return -inf).
    """
    tau = np.ones_like(lam)
    m00 = (home_goals == 0) & (away_goals == 0)
    m01 = (home_goals == 0) & (away_goals == 1)
    m10 = (home_goals == 1) & (away_goals == 0)
    m11 = (home_goals == 1) & (away_goals == 1)
    tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
    tau[m01] = 1.0 + lam[m01] * rho
    tau[m10] = 1.0 + mu[m10] * rho
    tau[m11] = 1.0 - rho
    return np.log(np.maximum(tau, 1e-10))


def _unpack(
    theta: NDArray[np.float64], n_teams: int, fit_rho: bool
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float]:
    """Map the free parameter vector to (attack, defense, gamma, rho).

    Layout: ``[attack_free (n-1), defense_free (n-1), gamma, (rho)]``. The dropped
    nth attack/defense is reconstructed as minus the sum of the free ones, which
    is exactly the sum-to-zero gauge.
    """
    k = n_teams - 1
    attack_free = theta[:k]
    defense_free = theta[k : 2 * k]
    gamma = float(theta[2 * k])
    attack = np.append(attack_free, -attack_free.sum())
    defense = np.append(defense_free, -defense_free.sum())
    rho = float(theta[2 * k + 1]) if fit_rho else 0.0
    return attack, defense, gamma, rho


def _neg_log_likelihood(
    theta: NDArray[np.float64],
    data: MatchData,
    gammaln_home: NDArray[np.float64],
    gammaln_away: NDArray[np.float64],
    fit_rho: bool,
) -> float:
    """Weighted negative log-likelihood — the function scipy minimizes.

    Uses ``log P(k; lam) = k*log(lam) - lam - log(k!)`` with ``log(k!)``
    precomputed via ``gammaln`` (the goals never change across iterations), so
    each evaluation is two exponentials and some array math.
    """
    attack, defense, gamma, rho = _unpack(theta, data.n_teams, fit_rho)

    log_lambda = attack[data.home_idx] + defense[data.away_idx] + gamma
    log_mu = attack[data.away_idx] + defense[data.home_idx]
    lam = np.exp(log_lambda)
    mu = np.exp(log_mu)

    log_lik = (
        data.home_goals * log_lambda
        - lam
        - gammaln_home
        + data.away_goals * log_mu
        - mu
        - gammaln_away
    )
    if fit_rho:
        log_lik = log_lik + _log_tau(data.home_goals, data.away_goals, lam, mu, rho)

    return -float(np.sum(data.weights * log_lik))


def _fit(data: MatchData, *, fit_rho: bool, max_iter: int) -> TeamRatings:
    n = data.n_teams
    if n < 2:
        raise ValueError("need at least two teams to fit")

    # log(k!) is constant across the optimization; compute it once.
    gammaln_home = gammaln(data.home_goals + 1)
    gammaln_away = gammaln(data.away_goals + 1)

    n_strength = 2 * (n - 1)
    x0 = np.zeros(n_strength + 1 + (1 if fit_rho else 0))
    x0[n_strength] = _INIT_HOME_ADV  # gamma
    bounds: list[tuple[float | None, float | None]] = [(None, None)] * (n_strength + 1)
    if fit_rho:
        x0[n_strength + 1] = _INIT_RHO
        bounds.append(_RHO_BOUNDS)

    result = minimize(
        _neg_log_likelihood,
        x0,
        args=(data, gammaln_home, gammaln_away, fit_rho),
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": max_iter},
    )

    attack, defense, gamma, rho = _unpack(result.x, n, fit_rho)
    return TeamRatings(
        teams=data.teams,
        attack=attack,
        defense=defense,
        home_adv=gamma,
        rho=rho,
        log_likelihood=-float(result.fun),
    )


def match_log_likelihood(ratings: TeamRatings, data: MatchData) -> float:
    """Weighted log-likelihood of ``data`` under fixed ``ratings``.

    Unlike the optimizer's objective this takes an already-fitted model, so it's
    the natural out-of-sample score for holdout evaluation (e.g. picking the
    time-decay xi). With ``weights`` all ones it's the plain summed log-likelihood.
    """
    attack, defense = ratings.attack, ratings.defense
    log_lambda = attack[data.home_idx] + defense[data.away_idx] + ratings.home_adv
    log_mu = attack[data.away_idx] + defense[data.home_idx]
    lam = np.exp(log_lambda)
    mu = np.exp(log_mu)

    log_lik = (
        data.home_goals * log_lambda
        - lam
        - gammaln(data.home_goals + 1)
        + data.away_goals * log_mu
        - mu
        - gammaln(data.away_goals + 1)
    )
    if ratings.rho != 0.0:
        log_lik = log_lik + _log_tau(data.home_goals, data.away_goals, lam, mu, ratings.rho)

    return float(np.sum(data.weights * log_lik))


def fit_independent_poisson(data: MatchData, *, max_iter: int = 200) -> TeamRatings:
    """Fit the baseline independent-Poisson model (rho fixed at 0)."""
    return _fit(data, fit_rho=False, max_iter=max_iter)


def fit_dixon_coles(data: MatchData, *, max_iter: int = 200) -> TeamRatings:
    """Fit the full Dixon-Coles model, estimating rho jointly with the strengths."""
    return _fit(data, fit_rho=True, max_iter=max_iter)
