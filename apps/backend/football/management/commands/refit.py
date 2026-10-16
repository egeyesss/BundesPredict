from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.data.footballdata import DownloadError
from bundespredict.data.seasons import results_season_start, season_code
from football.services.paths import data_dir
from football.services.results import download_season, ingest_directory
from football.services.training import DEFAULT_XI, refit_serving_model

from ._options import today_utc


class Command(BaseCommand):
    help = (
        "Refresh results, fit Dixon-Coles on everything played before the cutoff and store it "
        "as the newest serving run. Re-running without new results changes nothing."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--skip-download",
            action="store_true",
            help="train on the matches already in the database",
        )
        parser.add_argument(
            "--select-xi",
            action="store_true",
            help="re-select the time-decay rate walk-forward instead of the default",
        )
        parser.add_argument(
            "--xi", type=float, default=None, help=f"decay rate override (default {DEFAULT_XI})"
        )
        parser.add_argument(
            "--as-of",
            type=date.fromisoformat,
            default=None,
            help="cutoff date YYYY-MM-DD; only earlier matches are used (default today)",
        )
        parser.add_argument(
            "--force", action="store_true", help="store a new run even if an identical one exists"
        )
        parser.add_argument(
            "--raw-dir", default=None, help="directory holding D1_<season>.csv (default data/raw)"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        as_of = options["as_of"] or today_utc()
        ingested = ""
        if not options["skip_download"]:
            raw_dir = Path(options["raw_dir"]) if options["raw_dir"] else data_dir() / "raw"
            code = season_code(results_season_start(as_of))
            try:
                download_season(code, raw_dir)
            except DownloadError as exc:
                raise CommandError(f"could not download season {code}: {exc}") from exc
            files, summary = ingest_directory(raw_dir)
            ingested = (
                f"; ingested {files} files ({summary.created} new, {summary.updated} updated "
                f"matches)"
            )

        try:
            outcome = refit_serving_model(
                as_of=as_of,
                xi=options["xi"],
                select_xi_on_history=options["select_xi"],
                force=options["force"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        verb = "created run" if outcome.created else "unchanged, run"
        self.stdout.write(
            f"refit: {verb} {outcome.run.id} on {outcome.n_matches} matches before {as_of} "
            f"(xi={outcome.xi:.4f}, rho={outcome.ratings.rho:.3f}, "
            f"home_adv={outcome.ratings.home_adv:.3f}, {len(outcome.ratings.teams)} teams, "
            f"{outcome.squad_values_used} squad values){ingested}"
        )
