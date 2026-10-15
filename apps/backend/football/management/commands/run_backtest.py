from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.model.time_decay import select_xi
from football.services.backtest import WalkForwardStore, run_walk_forward
from football.services.training import load_dated_matches

logger = logging.getLogger(__name__)

DEFAULT_MIN_TRAIN_MATCHES = 200


class Command(BaseCommand):
    help = (
        "Run the walk-forward backtest (refit every gameweek on results strictly before it) "
        "and store one walk-forward model run per gameweek. Re-running replaces nothing that "
        "has not changed."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--xi",
            type=float,
            default=None,
            help="decay rate (default: selected walk-forward on the full history)",
        )
        parser.add_argument(
            "--min-train-matches",
            type=int,
            default=DEFAULT_MIN_TRAIN_MATCHES,
            help="skip gameweeks with less history than this",
        )
        parser.add_argument(
            "--no-plot", action="store_true", help="skip the reliability plot (needs matplotlib)"
        )
        parser.add_argument(
            "--report-dir",
            default=None,
            help="also score the run and write backtest_report.md and reliability.png here",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        xi = options["xi"]
        if xi is None:
            dated = load_dated_matches(as_of=None)
            selected = select_xi(
                dated.teams,
                dated.home_idx,
                dated.away_idx,
                dated.home_goals,
                dated.away_goals,
                dated.day_ordinal,
            )
            xi = selected.xi

        store = WalkForwardStore()
        try:
            result = run_walk_forward(
                xi=xi, min_train_matches=options["min_train_matches"], store=store
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        runs = store.prune()

        line = (
            f"run_backtest: {len(result)} predictions over seasons {min(result.seasons)} to "
            f"{max(result.seasons)} (xi={xi:.4f}); walk-forward runs: {runs.reused} reused, "
            f"{runs.created} created, {runs.removed} removed"
        )
        if options["report_dir"]:
            from bundespredict.eval.report import build_report

            xg_result = run_walk_forward(
                xi=xi,
                min_train_matches=options["min_train_matches"],
                store=None,
                use_xg=True,
            )
            report = build_report(
                result,
                xg_result,
                xi=xi,
                reports_dir=Path(options["report_dir"]),
                plot=not options["no_plot"],
            )
            line += f"; report {report.report_path}"
        self.stdout.write(line)
