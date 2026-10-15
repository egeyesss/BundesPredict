from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.data import understat, understat_scrape
from football.services.paths import data_dir
from football.services.xg import ingest_xg


class Command(BaseCommand):
    help = (
        "Cache Understat per-match xG with a local browser, then backfill matches.home_xg and "
        "away_xg. Understat sits behind Cloudflare, so the fetch only works from a machine "
        "where a headed Chromium can load the page."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--seasons",
            type=int,
            nargs="*",
            help=(
                f"season start years (default {understat_scrape.FIRST_SEASON}.."
                f"{understat_scrape.LAST_SEASON})"
            ),
        )
        parser.add_argument("--headless", action="store_true", help="run Chromium headless")
        parser.add_argument(
            "--skip-fetch", action="store_true", help="don't scrape; use the cache as it is"
        )
        parser.add_argument(
            "--skip-ingest", action="store_true", help="only cache the pages; leave matches alone"
        )
        parser.add_argument(
            "--cache-dir", default=None, help="page cache (default data/understat_cache)"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        cache_dir = (
            Path(options["cache_dir"]) if options["cache_dir"] else data_dir() / "understat_cache"
        )
        years = (
            []
            if options["skip_fetch"]
            else options["seasons"]
            or list(range(understat_scrape.FIRST_SEASON, understat_scrape.LAST_SEASON + 1))
        )
        headless = options["headless"]
        scraped = understat_scrape.scrape_seasons(
            cache_dir,
            years,
            fetch=lambda year: understat_scrape.fetch_season(year, headless=headless),
        )
        if years and not scraped:
            raise CommandError("nothing was cached; see the errors above")

        if options["skip_ingest"]:
            self.stdout.write(f"scrape_understat: cached {len(scraped)} seasons, ingest skipped")
            return
        if not cache_dir.exists() or not any(cache_dir.glob("bundesliga_*.json")):
            raise CommandError(f"no cached seasons to ingest in {cache_dir}")

        summary = ingest_xg(understat.load_cache(cache_dir))
        self.stdout.write(
            f"scrape_understat: cached {len(scraped)} seasons; {summary.seasons} seasons ingested, "
            f"{summary.parsed} parsed, {summary.matched} matched, {summary.unmatched} unmatched, "
            f"{summary.updated} updated"
        )
