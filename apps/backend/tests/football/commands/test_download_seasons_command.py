from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from django.core.management.base import CommandError

from bundespredict.data.footballdata import DownloadError
from football.services import results

RECORDED = b"Div,Date,HomeTeam,AwayTeam\n"


@pytest.fixture
def requested(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    codes: list[str] = []

    def recorded_response(code: str) -> bytes:
        codes.append(code)
        return RECORDED

    monkeypatch.setattr(results, "fetch_season_csv", recorded_response)
    return codes


def test_start_and_end_years_expand_to_season_codes(
    tmp_path: Path, requested: list[str], run_command: Callable[..., str]
) -> None:
    summary = run_command("download_seasons", start=2022, end=2024, raw_dir=str(tmp_path))

    assert requested == ["2223", "2324", "2425"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "D1_2223.csv",
        "D1_2324.csv",
        "D1_2425.csv",
    ]
    assert summary == "download_seasons: 3 seasons, 3 written, 0 unchanged"


def test_explicit_season_codes_are_downloaded_as_given(
    tmp_path: Path, requested: list[str], run_command: Callable[..., str]
) -> None:
    run_command("download_seasons", seasons=["2324", "2223"], raw_dir=str(tmp_path))

    assert requested == ["2324", "2223"]


def test_an_identical_file_is_left_alone(
    tmp_path: Path, requested: list[str], run_command: Callable[..., str]
) -> None:
    run_command("download_seasons", seasons=["2324"], raw_dir=str(tmp_path))

    summary = run_command("download_seasons", seasons=["2324"], raw_dir=str(tmp_path))

    assert summary == "download_seasons: 1 seasons, 0 written, 1 unchanged"


def test_a_changed_file_is_overwritten(
    tmp_path: Path, requested: list[str], run_command: Callable[..., str]
) -> None:
    (tmp_path / "D1_2324.csv").write_bytes(b"stale")

    summary = run_command("download_seasons", seasons=["2324"], raw_dir=str(tmp_path))

    assert (tmp_path / "D1_2324.csv").read_bytes() == RECORDED
    assert summary.endswith("1 written, 0 unchanged")


def test_a_failed_season_does_not_stop_the_others_but_fails_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_command: Callable[..., str]
) -> None:
    def flaky(code: str) -> bytes:
        if code == "2324":
            raise DownloadError("2324: HTTP 503")
        return RECORDED

    monkeypatch.setattr(results, "fetch_season_csv", flaky)

    with pytest.raises(CommandError, match="2324: HTTP 503"):
        run_command("download_seasons", seasons=["2223", "2324", "2425"], raw_dir=str(tmp_path))

    assert (tmp_path / "D1_2223.csv").exists()
    assert (tmp_path / "D1_2425.csv").exists()


@pytest.mark.parametrize(
    "options",
    [{}, {"start": 2022}, {"start": 2024, "end": 2022}],
    ids=["nothing", "start-only", "reversed"],
)
def test_the_season_range_must_be_complete_and_ordered(
    tmp_path: Path, requested: list[str], run_command: Callable[..., str], options: dict[str, int]
) -> None:
    with pytest.raises(CommandError):
        run_command("download_seasons", raw_dir=str(tmp_path), **options)

    assert requested == []
