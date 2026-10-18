from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from bundespredict.eval.backtest import DEFAULT_XI
from football.services.promoted_prior import evaluate_promoted_prior

from .run_backtest import DEFAULT_MIN_TRAIN_MATCHES


class Command(BaseCommand):
    help = (
        "Score the squad-value shrinkage prior against league-mean shrinkage on promoted teams' "
        "first matches back up. Reads the database and writes nothing."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--xi", type=float, default=DEFAULT_XI, help="decay rate")
        parser.add_argument(
            "--min-train-matches",
            type=int,
            default=DEFAULT_MIN_TRAIN_MATCHES,
            help="skip gameweeks with less history than this",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            report = evaluate_promoted_prior(
                xi=options["xi"], min_train_matches=options["min_train_matches"]
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"promoted-team early matches: {report.early_matches} of {report.predictions} "
            "predictions"
        )
        for score in report.scores:
            self.stdout.write(
                f"{score.label:>20}: promoted-slice RPS {score.slice_rps:.4f} "
                f"(log-loss {score.slice_log_loss:.4f}) | overall RPS {score.overall_rps:.4f}"
            )
