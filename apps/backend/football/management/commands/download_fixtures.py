from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.data import fixtures as openligadb
from bundespredict.data.seasons import schedule_season_start, season_code
from football.services.schedule import sync_fixtures

from ._options import today_utc


class Command(BaseCommand):
    help = "Mirror the upcoming Bundesliga schedule from OpenLigaDB into the fixtures table."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="season start year, e.g. 2026 for 2026/27 (default: inferred from today)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        season = options["season"]
        if season is None:
            season = schedule_season_start(today_utc())
        try:
            payload = openligadb.fetch_season_json(season)
        except OSError as exc:
            raise CommandError(f"could not fetch the {season} schedule: {exc}") from exc

        summary = sync_fixtures(openligadb.parse_fixtures(payload, season))
        self.stdout.write(
            f"download_fixtures: season {season_code(season)}, {summary.stored} upcoming fixtures "
            f"({summary.created} created, {summary.updated} updated, {summary.removed} removed, "
            f"{summary.unchanged} unchanged)"
        )
