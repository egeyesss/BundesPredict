from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from track_record.resolution import resolve_predictions


class Command(BaseCommand):
    help = "Score frozen predictions whose fixtures have a result in the matches table."

    def handle(self, *args: Any, **options: Any) -> None:
        report = resolve_predictions()

        count = len(report.resolved)
        self.stdout.write(f"resolved {count} fixture{'' if count == 1 else 's'}")
        for resolution in report.resolved:
            fixture = resolution.prediction.fixture
            self.stdout.write(
                f"  MD{fixture.matchday}  {fixture.home.name} "
                f"{resolution.home_goals}-{resolution.away_goals} {fixture.away.name}"
            )
        self.stdout.write(f"{len(report.unresolved)} still without a result")
