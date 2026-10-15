"""The shared fit-and-shrink recipe matches the steps the refit script used to inline."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from bundespredict.data.dated_matches import DatedMatches, MatchRecord
from bundespredict.data.fitting import fit_shrunk_ratings
from bundespredict.model.dixon_coles import fit_dixon_coles
from bundespredict.model.shrinkage import shrink_ratings, team_match_counts

TEAMS = ("Alpha", "Beta", "Gamma", "Delta")


def _history() -> DatedMatches:
    rng = np.random.default_rng(11)
    records = []
    day = date(2024, 1, 1).toordinal()
    for _ in range(6):
        for home in TEAMS:
            for away in TEAMS:
                if home != away:
                    records.append(
                        MatchRecord(
                            home,
                            away,
                            int(rng.poisson(1.6)),
                            int(rng.poisson(1.1)),
                            date.fromordinal(day),
                        )
                    )
                    day += 1
    return DatedMatches.from_records(records)


def test_matches_a_manual_fit_then_shrink() -> None:
    dated = _history()
    reference = date(2025, 1, 1)

    data = dated.to_match_data(xi=0.004, reference=reference)
    expected = shrink_ratings(fit_dixon_coles(data), team_match_counts(data))
    actual = fit_shrunk_ratings(dated, xi=0.004, reference=reference)

    assert actual.teams == expected.teams
    assert actual.attack == pytest.approx(expected.attack, abs=1e-12)
    assert actual.defense == pytest.approx(expected.defense, abs=1e-12)
    assert actual.rho == pytest.approx(expected.rho, abs=1e-12)


def test_squad_values_change_the_shrinkage_target() -> None:
    dated = _history()
    reference = date(2025, 1, 1)
    values = {"Alpha": 900_000_000, "Beta": 400_000_000, "Gamma": 200_000_000, "Delta": 50_000_000}

    plain = fit_shrunk_ratings(dated, xi=0.004, reference=reference)
    valued = fit_shrunk_ratings(dated, xi=0.004, reference=reference, season_values=values)

    assert not np.allclose(plain.attack, valued.attack)
