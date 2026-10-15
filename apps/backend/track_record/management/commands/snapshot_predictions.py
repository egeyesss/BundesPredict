from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from track_record.snapshots import NoModelRunError, snapshot_upcoming


class Command(BaseCommand):
    help = "Freeze the base model's prediction for each fixture kicking off in the next 48 hours."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            report = snapshot_upcoming()
        except NoModelRunError as error:
            raise CommandError(f"cannot snapshot without a model run: {error}") from error

        count = len(report.created)
        self.stdout.write(f"froze {count} fixture{'' if count == 1 else 's'}")
        for snapshot in report.created:
            fixture = snapshot.fixture
            self.stdout.write(
                f"  {fixture.kickoff_utc:%Y-%m-%d %H:%M}Z  MD{fixture.matchday}  "
                f"{fixture.home.name} v {fixture.away.name}  "
                f"H {snapshot.p_home:.3f}  D {snapshot.p_draw:.3f}  A {snapshot.p_away:.3f}  "
                f"(run {snapshot.model_run_id})"
            )

        if report.skipped_without_ratings:
            names = ", ".join(
                f"{f.home.name} v {f.away.name}" for f in report.skipped_without_ratings
            )
            raise CommandError(f"no ratings in the newest model run for: {names}")
