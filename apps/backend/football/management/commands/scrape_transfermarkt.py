from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.data import tm_scrape
from bundespredict.data.seasons import results_season_start
from football.services.paths import data_dir
from football.services.squads import ingest_snapshot

from ._options import today_utc


class Command(BaseCommand):
    help = (
        "Scrape Transfermarkt squads and market values into the cache, then store the snapshot. "
        "The cache is the source of truth, so a failed scrape keeps the previous snapshot."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--skip-fetch",
            action="store_true",
            help="ingest from the existing cache without touching the network",
        )
        parser.add_argument("--cache-dir", default=None, help="page cache (default data/tm_cache)")

    def handle(self, *args: Any, **options: Any) -> None:
        cache_dir = Path(options["cache_dir"]) if options["cache_dir"] else data_dir() / "tm_cache"
        current_year = results_season_start(today_utc())
        if not options["skip_fetch"]:
            try:
                tm_scrape.fetch_all(cache_dir, current_year, fetch=tm_scrape.polite_fetch)
            except OSError as exc:
                raise CommandError(f"Transfermarkt fetch failed: {exc}") from exc

        summary = ingest_snapshot(tm_scrape.read_cache(cache_dir, current_year))
        self.stdout.write(
            f"scrape_transfermarkt: {summary.teams_linked} teams linked, "
            f"{summary.players_stored} players ({summary.players_removed} removed), "
            f"{summary.squad_values_stored} squad values, {summary.changed} rows changed"
        )
