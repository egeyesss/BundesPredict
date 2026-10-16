from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from django.core.management.base import CommandError

from bundespredict.model.dixon_coles import TeamRatings
from football import repositories
from football.models import Match, ModelRun, SquadValue, Team, TeamParam
from football.services import results

pytestmark = pytest.mark.django_db

SEASON_BOUNDARY = date(2024, 6, 1)  # after 2324, before the first 2425 match (2024-08-24)
TOLERANCE = 1e-9


def params_by_team(run: ModelRun) -> dict[str, tuple[float, float]]:
    return {
        name: (attack, defense)
        for name, attack, defense in TeamParam.objects.filter(model_run=run).values_list(
            "team__name", "attack", "defense"
        )
    }


@pytest.fixture
def refit_as_of_boundary(loaded_results: Path, run_command: Callable[..., str]) -> str:
    return run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY)


def test_refit_uses_only_matches_before_the_cutoff(
    loaded_results: Path, run_command: Callable[..., str]
) -> None:
    summary = run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY)

    run = ModelRun.objects.get()
    assert run.n_matches == 60
    assert run.as_of_date == SEASON_BOUNDARY
    assert summary.startswith(f"refit: created run {run.id} on 60 matches before 2024-06-01")


def test_a_cutoff_is_strict_so_a_match_on_that_day_is_left_out(
    loaded_results: Path, run_command: Callable[..., str]
) -> None:
    match_day = Match.objects.order_by("date").last()
    assert match_day is not None

    run_command("refit", skip_download=True, as_of=match_day.date)

    assert ModelRun.objects.get().n_matches == Match.objects.filter(date__lt=match_day.date).count()


def test_later_matches_cannot_change_a_cutoff_fit(
    loaded_results: Path, run_command: Callable[..., str]
) -> None:
    run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY)
    with_later_matches = ModelRun.objects.get()
    assert Match.objects.filter(date__gte=SEASON_BOUNDARY).exists()

    Match.objects.filter(date__gte=SEASON_BOUNDARY).delete()
    run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY)

    assert ModelRun.objects.count() == 1, "same parameters, so the existing run is reused"
    assert params_by_team(ModelRun.objects.get()) == params_by_team(with_later_matches)


def test_a_cutoff_fit_differs_from_a_fit_that_sees_the_later_season(
    loaded_results: Path, run_command: Callable[..., str], today: date
) -> None:
    run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY)
    run_command("refit", skip_download=True, as_of=today)

    early, late = ModelRun.objects.order_by("as_of_date")
    assert (early.n_matches, late.n_matches) == (60, 90)
    early_params, late_params = params_by_team(early), params_by_team(late)
    assert any(abs(early_params[t][0] - late_params[t][0]) > 1e-3 for t in early_params), (
        "the extra season has to move the fit, or the cutoff test above proves nothing"
    )


def test_second_run_changes_no_rows(
    refit_as_of_boundary: str,
    run_command: Callable[..., str],
    table_rows: Callable[[Any], list[tuple[object, ...]]],
) -> None:
    models = (ModelRun, TeamParam, Match, Team)
    before = {model: table_rows(model) for model in models}

    summary = run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY)

    assert summary.startswith(f"refit: unchanged, run {ModelRun.objects.get().id} on 60 matches")
    assert {model: table_rows(model) for model in models} == before


def test_force_stores_another_run(
    refit_as_of_boundary: str, run_command: Callable[..., str]
) -> None:
    run_command("refit", skip_download=True, as_of=SEASON_BOUNDARY, force=True)

    first, second = ModelRun.objects.order_by("id")
    assert params_by_team(first) == params_by_team(second)


def test_new_results_produce_a_new_run(
    loaded_results: Path, run_command: Callable[..., str], today: date
) -> None:
    run_command("refit", skip_download=True, as_of=today)
    Match.objects.filter(season="2425").order_by("-date", "-id").first().delete()  # type: ignore[union-attr]

    run_command("refit", skip_download=True, as_of=today)

    assert sorted(ModelRun.objects.values_list("n_matches", flat=True)) == [89, 90]


def test_the_newest_run_serves_predictions(
    loaded_results: Path, run_command: Callable[..., str], today: date
) -> None:
    run_command("refit", skip_download=True, as_of=today)

    run = repositories.latest_model_run()
    assert run is not None
    params = repositories.team_params_for(run)
    ratings = TeamRatings(
        teams=tuple(p.team.name for p in params),
        attack=np.array([p.attack for p in params]),
        defense=np.array([p.defense for p in params]),
        home_adv=run.home_adv,
        rho=run.rho,
        log_likelihood=run.log_likelihood,
        xg_coef=run.xg_coef,
    )
    market = ratings.predict("Bayern Munich", "SC Freiburg")
    assert market.p_home + market.p_draw + market.p_away == pytest.approx(1.0)
    strong_home = market.p_home
    assert strong_home > ratings.predict("SC Freiburg", "Bayern Munich").p_home


def test_explicit_xi_is_recorded_on_the_run(
    loaded_results: Path, run_command: Callable[..., str], today: date
) -> None:
    run_command("refit", skip_download=True, as_of=today, xi=0.002)

    assert ModelRun.objects.get().xi == 0.002


def test_squad_values_shift_the_shrinkage_prior(
    loaded_results: Path, run_command: Callable[..., str], today: date
) -> None:
    run_command("refit", skip_download=True, as_of=today, force=True)
    without_values = params_by_team(ModelRun.objects.get())
    for team, value in zip(Team.objects.order_by("name"), range(1, 7), strict=True):
        SquadValue.objects.create(
            season="2425",
            team=team,
            value_eur=value * 100_000_000,
            scraped_at="2025-05-01T00:00:00Z",
        )

    summary = run_command("refit", skip_download=True, as_of=today)

    assert "6 squad values" in summary
    with_values = params_by_team(ModelRun.objects.latest("id"))
    assert with_values != without_values


def test_download_ingests_the_current_season_before_fitting(
    results_csv_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_command: Callable[..., str],
    today: date,
) -> None:
    recorded = (results_csv_dir / "D1_2425.csv").read_bytes()
    monkeypatch.setattr(results, "fetch_season_csv", lambda code: recorded)
    monkeypatch.setattr("football.management.commands.refit.today_utc", lambda: today)

    summary = run_command("refit", raw_dir=str(tmp_path / "fresh_raw"))

    assert ModelRun.objects.get().n_matches == 30
    assert summary.endswith("; ingested 1 files (30 new, 0 updated matches)")


def test_refit_without_matches_is_reported(
    tmp_path: Path, run_command: Callable[..., str], today: date
) -> None:
    with pytest.raises(CommandError, match="no matches"):
        run_command("refit", skip_download=True, as_of=today)
