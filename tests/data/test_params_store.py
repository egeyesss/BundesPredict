"""Round-trip tests for persisting fitted parameters."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from bundespredict.data.models import Team, TeamParam
from bundespredict.data.params_store import latest_run_id, load_ratings, save_ratings
from bundespredict.model.dixon_coles import TeamRatings


def _seed_teams(session: Session, names: list[str]) -> None:
    session.add_all([Team(name=n) for n in names])
    session.commit()


def _ratings(teams: tuple[str, ...], rho: float = -0.12) -> TeamRatings:
    # Sum-to-zero strengths so the round-trip mirrors a real (gauge-fixed) fit.
    attack = np.array([0.4, -0.1, -0.3], dtype=np.float64)
    defense = np.array([-0.2, 0.25, -0.05], dtype=np.float64)
    return TeamRatings(
        teams=teams,
        attack=attack,
        defense=defense,
        home_adv=0.3,
        rho=rho,
        log_likelihood=-1234.5,
    )


def test_save_then_load_round_trips(session: Session) -> None:
    names = ["FC Bayern München", "Borussia Dortmund", "1.FC Köln"]
    _seed_teams(session, names)
    ratings = _ratings(tuple(names))

    run_id = save_ratings(session, ratings, xi=0.004, n_matches=900, as_of_date=date(2024, 5, 1))
    loaded = load_ratings(session, run_id)

    # Teams come back name-sorted; each team's strengths must follow its name.
    assert loaded.teams == tuple(sorted(names))
    for name in names:
        i, j = ratings.index(name), loaded.index(name)
        assert loaded.attack[j] == pytest.approx(ratings.attack[i])
        assert loaded.defense[j] == pytest.approx(ratings.defense[i])
    assert loaded.home_adv == pytest.approx(0.3)
    assert loaded.rho == pytest.approx(-0.12)
    assert loaded.log_likelihood == pytest.approx(-1234.5)


def test_run_records_metadata_and_model_type(session: Session) -> None:
    names = ["FC Bayern München", "Borussia Dortmund", "1.FC Köln"]
    _seed_teams(session, names)

    dc_id = save_ratings(session, _ratings(tuple(names), rho=-0.12), xi=0.004, n_matches=900)
    ip_id = save_ratings(session, _ratings(tuple(names), rho=0.0), xi=0.0, n_matches=900)

    from bundespredict.data.models import ModelRun

    dc = session.get(ModelRun, dc_id)
    ip = session.get(ModelRun, ip_id)
    assert dc is not None and ip is not None
    assert dc.model_type == "dixon_coles"
    assert ip.model_type == "independent_poisson"
    assert dc.xi == pytest.approx(0.004)
    assert len(session.execute(select(TeamParam).where(TeamParam.model_run_id == dc_id)).all()) == 3


def test_save_rejects_unknown_team(session: Session) -> None:
    _seed_teams(session, ["FC Bayern München", "Borussia Dortmund"])
    ratings = _ratings(("FC Bayern München", "Borussia Dortmund", "Phantom FC"))
    with pytest.raises(ValueError, match="Phantom FC"):
        save_ratings(session, ratings, xi=0.0, n_matches=10)


def test_latest_run_id_tracks_recency_and_cutoff(session: Session) -> None:
    names = ["FC Bayern München", "Borussia Dortmund", "1.FC Köln"]
    _seed_teams(session, names)
    ratings = _ratings(tuple(names))

    assert latest_run_id(session) is None
    first = save_ratings(session, ratings, xi=0.004, n_matches=1, as_of_date=date(2024, 1, 1))
    second = save_ratings(session, ratings, xi=0.004, n_matches=1, as_of_date=date(2024, 2, 1))

    assert latest_run_id(session) == second
    assert latest_run_id(session, as_of_date=date(2024, 1, 1)) == first
    assert latest_run_id(session, as_of_date=date(2099, 1, 1)) is None
