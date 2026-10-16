from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.data.footballdata import DownloadError
from bundespredict.data.seasons import results_season_start, season_code
from football.services.paths import data_dir
from football.services.results import download_season, ingest_directory

from ._options import today_utc


class Command(BaseCommand):
    help = "Ingest football-data season CSVs from the raw directory into the matches table."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--raw-dir", default=None, help="directory holding D1_<season>.csv (default data/raw)"
        )
        parser.add_argument(
            "--download",
            action="store_true",
            help="refresh the current season's CSV from football-data.co.uk first",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        raw_dir = Path(options["raw_dir"]) if options["raw_dir"] else data_dir() / "raw"
        if options["download"]:
            code = season_code(results_season_start(today_utc()))
            try:
                download_season(code, raw_dir)
            except DownloadError as exc:
                raise CommandError(f"could not download season {code}: {exc}") from exc

        files, summary = ingest_directory(raw_dir)
        self.stdout.write(
            f"ingest_results: {files} files, {summary.total} matches "
            f"({summary.created} created, {summary.updated} updated, "
            f"{summary.unchanged} unchanged)"
        )
