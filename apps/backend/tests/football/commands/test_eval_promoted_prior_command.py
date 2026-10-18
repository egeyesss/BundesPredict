from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.core.management.base import CommandError

from football.models import Match, ModelRun, SquadValue, Team

pytestmark = pytest.mark.django_db

MIN_TRAIN = 20
SLICE_RPS = re.compile(r"promoted-slice RPS (\d\.\d{4})")


@pytest.fixture
def promoted_results(results_csv_dir: Path, run_command: Callable[..., str]) -> None:
    # Hoffenheim replaces Stuttgart in 2425, so it is the one promoted club in the data.
    csv_2425 = results_csv_dir / "D1_2425.csv"
    csv_2425.write_text(csv_2425.read_text().replace("Stuttgart", "Hoffenheim"))
    run_command("ingest_results", raw_dir=str(results_csv_dir))


@pytest.fixture
def squad_values(promoted_results: None) -> None:
    scraped_at = datetime(2024, 8, 1, tzinfo=UTC)
    # Values must differ between the established clubs, or the regression has no slope.
    values = {"TSG 1899 Hoffenheim": 900_000_000}
    for index, team in enumerate(Team.objects.order_by("name")):
        for season in set(Match.objects.values_list("season", flat=True)):
            SquadValue.objects.create(
                season=season,
                team=team,
                value_eur=values.get(team.name, 100_000_000 * (index + 1)),
                scraped_at=scraped_at,
            )


def test_scores_both_priors_on_the_promoted_teams_first_matches(
    squad_values: None, run_command: Callable[..., str]
) -> None:
    report = run_command("eval_promoted_prior", min_train_matches=MIN_TRAIN)

    header, league_mean, value_implied = report.splitlines()
    assert re.fullmatch(r"promoted-team early matches: [1-9]\d* of \d+ predictions", header)
    assert league_mean.lstrip().startswith("league-mean prior:")
    assert value_implied.lstrip().startswith("value-implied prior:")
    slices = [SLICE_RPS.search(line) for line in (league_mean, value_implied)]
    assert all(slices)
    assert slices[0].group(1) != slices[1].group(1)  # type: ignore[union-attr]


def test_it_leaves_the_database_alone(squad_values: None, run_command: Callable[..., str]) -> None:
    run_command("eval_promoted_prior", min_train_matches=MIN_TRAIN)

    assert ModelRun.objects.count() == 0


def test_it_needs_squad_values(promoted_results: None, run_command: Callable[..., str]) -> None:
    with pytest.raises(CommandError, match="scrape_transfermarkt"):
        run_command("eval_promoted_prior", min_train_matches=MIN_TRAIN)
