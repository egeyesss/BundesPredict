from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from football import repositories
from football.models import Match, ModelRun, TeamParam

pytestmark = pytest.mark.django_db

MIN_TRAIN = 20


def walk_forward_runs() -> list[ModelRun]:
    return list(ModelRun.objects.filter(version="walk-forward").order_by("as_of_date"))


@pytest.fixture
def backtested(loaded_results: Path, run_command: Callable[..., str]) -> str:
    return run_command("run_backtest", xi=0.004, min_train_matches=MIN_TRAIN)


def test_one_run_is_stored_per_predicted_gameweek(backtested: str) -> None:
    runs = walk_forward_runs()

    # 2223 is warmup, 2324 and 2425 are predicted: 10 gameweeks each.
    assert len(runs) == 20
    assert backtested.startswith("run_backtest: 60 predictions over seasons 2324 to 2425")
    assert f"walk-forward runs: 0 reused, {len(runs)} created, 0 removed" in backtested


def test_every_run_only_saw_matches_before_its_cutoff(backtested: str) -> None:
    for run in walk_forward_runs():
        assert run.as_of_date is not None
        assert run.n_matches == Match.objects.filter(date__lt=run.as_of_date).count()


def test_second_run_changes_no_rows(
    backtested: str,
    run_command: Callable[..., str],
    table_rows: Callable[[Any], list[tuple[object, ...]]],
) -> None:
    before = {model: table_rows(model) for model in (ModelRun, TeamParam)}

    summary = run_command("run_backtest", xi=0.004, min_train_matches=MIN_TRAIN)

    assert "20 reused, 0 created, 0 removed" in summary
    assert {model: table_rows(model) for model in before} == before


def test_gameweeks_that_drop_out_are_pruned(
    backtested: str, run_command: Callable[..., str]
) -> None:
    # Only the last five gameweeks of 2425 have 75+ earlier matches behind them.
    summary = run_command("run_backtest", xi=0.004, min_train_matches=75)

    assert "walk-forward runs: 5 reused, 0 created, 15 removed" in summary
    assert len(walk_forward_runs()) == 5


def test_walk_forward_runs_never_displace_the_serving_run(
    backtested: str, run_command: Callable[..., str], today: date
) -> None:
    run_command("refit", skip_download=True, as_of=today)
    serving = ModelRun.objects.get(version="serve")

    run_command("run_backtest", xi=0.004, min_train_matches=MIN_TRAIN)

    assert repositories.latest_model_run() == serving
    assert repositories.latest_model_run(as_of_date=walk_forward_runs()[0].as_of_date) is not None


def test_report_dir_gets_the_scored_report(
    loaded_results: Path, tmp_path: Path, run_command: Callable[..., str]
) -> None:
    summary = run_command(
        "run_backtest",
        xi=0.004,
        min_train_matches=MIN_TRAIN,
        report_dir=str(tmp_path / "reports"),
        no_plot=True,
    )

    report = (tmp_path / "reports" / "backtest_report.md").read_text()
    assert "# Backtest report" in report
    assert "model (calibrated)" in report
    assert summary.endswith(f"report {tmp_path / 'reports' / 'backtest_report.md'}")


def test_xi_is_selected_on_the_history_when_not_given(
    loaded_results: Path, run_command: Callable[..., str]
) -> None:
    summary = run_command("run_backtest", min_train_matches=MIN_TRAIN)

    assert "predictions over seasons" in summary
