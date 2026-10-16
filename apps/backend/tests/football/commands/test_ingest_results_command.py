from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from django.core.management.base import CommandError

from bundespredict.data.footballdata import DownloadError
from bundespredict.data.team_aliases import UnmappedTeamError
from football.models import Match, Team, TeamAlias
from football.services import results

pytestmark = pytest.mark.django_db


def test_ingest_stores_every_played_match(
    results_csv_dir: Path, run_command: Callable[..., str]
) -> None:
    summary = run_command("ingest_results", raw_dir=str(results_csv_dir))

    assert summary == "ingest_results: 3 files, 90 matches (90 created, 0 updated, 0 unchanged)"
    assert Match.objects.count() == 90
    assert set(Team.objects.values_list("name", flat=True)) == {
        "Bayern Munich",
        "Borussia Dortmund",
        "Bayer 04 Leverkusen",
        "RB Leipzig",
        "VfB Stuttgart",
        "SC Freiburg",
    }
    assert TeamAlias.objects.get(alias="Dortmund").team.name == "Borussia Dortmund"


def test_second_run_changes_no_rows(
    results_csv_dir: Path,
    run_command: Callable[..., str],
    table_rows: Callable[[Any], list[tuple[object, ...]]],
) -> None:
    run_command("ingest_results", raw_dir=str(results_csv_dir))
    before = {model: table_rows(model) for model in (Match, Team, TeamAlias)}

    summary = run_command("ingest_results", raw_dir=str(results_csv_dir))

    assert summary.endswith("(0 created, 0 updated, 90 unchanged)")
    assert {model: table_rows(model) for model in before} == before


def test_a_corrected_score_updates_only_that_match(
    results_csv_dir: Path, run_command: Callable[..., str]
) -> None:
    run_command("ingest_results", raw_dir=str(results_csv_dir))
    csv_path = results_csv_dir / "D1_2324.csv"
    lines = csv_path.read_text().splitlines()
    fields = lines[1].split(",")
    fields[5] = str(int(fields[5]) + 1)  # FTHG
    lines[1] = ",".join(fields)
    csv_path.write_text("\n".join(lines) + "\n")

    summary = run_command("ingest_results", raw_dir=str(results_csv_dir))

    assert summary.endswith("(0 created, 1 updated, 89 unchanged)")


def test_reingest_keeps_xg_filled_by_understat(
    loaded_results: Path, run_command: Callable[..., str]
) -> None:
    match = Match.objects.first()
    assert match is not None
    Match.objects.filter(pk=match.pk).update(home_xg=1.7, away_xg=0.4)

    run_command("ingest_results", raw_dir=str(loaded_results))

    match.refresh_from_db()
    assert (match.home_xg, match.away_xg) == (1.7, 0.4)


def test_unmapped_club_aborts_before_any_write(
    tmp_path: Path, run_command: Callable[..., str]
) -> None:
    (tmp_path / "D1_9999.csv").write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
        "D1,18/08/2023,15:30,Dortmund,Nowhere United,1,0,H\n"
    )

    with pytest.raises(UnmappedTeamError, match="Nowhere United"):
        run_command("ingest_results", raw_dir=str(tmp_path))

    assert Team.objects.count() == 0


def test_download_writes_the_current_season_file_then_ingests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_command: Callable[..., str], today: date
) -> None:
    recorded = (Path(__file__).parent / "results_csv" / "D1_2425.csv").read_bytes()
    requested: list[str] = []

    def recorded_response(code: str) -> bytes:
        requested.append(code)
        return recorded

    monkeypatch.setattr(results, "fetch_season_csv", recorded_response)
    monkeypatch.setattr("football.management.commands.ingest_results.today_utc", lambda: today)
    raw_dir = tmp_path / "raw"

    summary = run_command("ingest_results", raw_dir=str(raw_dir), download=True)

    assert requested == ["2425"]
    assert (raw_dir / "D1_2425.csv").read_bytes() == recorded
    assert summary == "ingest_results: 1 files, 30 matches (30 created, 0 updated, 0 unchanged)"


def test_failed_download_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_command: Callable[..., str]
) -> None:
    def blocked(code: str) -> bytes:
        raise DownloadError(f"{code}: HTTP 503")

    monkeypatch.setattr(results, "fetch_season_csv", blocked)

    with pytest.raises(CommandError, match="HTTP 503"):
        run_command("ingest_results", raw_dir=str(tmp_path), download=True)
