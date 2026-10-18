from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.data.footballdata import DownloadError
from bundespredict.data.seasons import season_code
from football.services.paths import data_dir
from football.services.results import download_season


class Command(BaseCommand):
    help = (
        "Download football-data season CSVs into the raw directory without touching the "
        "database. Run ingest_results afterwards to load them."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--start", type=int, help="first season start year, e.g. 2019")
        parser.add_argument("--end", type=int, help="last season start year, e.g. 2025")
        parser.add_argument(
            "--seasons", nargs="+", help="explicit season codes instead of a range, e.g. 2324 2223"
        )
        parser.add_argument(
            "--raw-dir", default=None, help="directory for D1_<season>.csv (default data/raw)"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        codes = self._season_codes(options)
        raw_dir = Path(options["raw_dir"]) if options["raw_dir"] else data_dir() / "raw"

        written = 0
        failures: list[str] = []
        for code in codes:
            try:
                written += download_season(code, raw_dir)
            except DownloadError as exc:
                failures.append(str(exc))
        if failures:
            raise CommandError("; ".join(failures))

        self.stdout.write(
            f"download_seasons: {len(codes)} seasons, {written} written, "
            f"{len(codes) - written} unchanged"
        )

    def _season_codes(self, options: dict[str, Any]) -> list[str]:
        if options["seasons"]:
            return list(options["seasons"])
        start, end = options["start"], options["end"]
        if start is None or end is None:
            raise CommandError("give --seasons, or both --start and --end")
        if start > end:
            raise CommandError("--start must not be after --end")
        return [season_code(year) for year in range(start, end + 1)]
