"""Kickoff text for the email: German time, plus the recipient's saved timezone when it differs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

GERMANY = ZoneInfo("Europe/Berlin")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class Kickoff:
    germany: str
    local: str | None

    @property
    def text(self) -> str:
        return self.germany if self.local is None else f"{self.germany} · {self.local}"


def _zone(name: str | None) -> tuple[ZoneInfo, str]:
    if name:
        try:
            return ZoneInfo(name), name.split("/")[-1].replace("_", " ")
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    return ZoneInfo("UTC"), "UTC"


def _clock(moment: datetime) -> str:
    return f"{moment:%H:%M}"


def format_kickoff(kickoff_utc: datetime, timezone_name: str | None) -> Kickoff:
    """ "Sat 15:30 Germany · 09:30 Toronto"; the weekday repeats only when the local day differs."""
    if kickoff_utc.tzinfo is None:
        raise ValueError("kickoff must be timezone-aware")
    in_germany = kickoff_utc.astimezone(GERMANY)
    zone, label = _zone(timezone_name)
    local = kickoff_utc.astimezone(zone)

    germany_text = f"{WEEKDAYS[in_germany.weekday()]} {_clock(in_germany)}"
    if _same_wall_time(in_germany, local):
        return Kickoff(germany=f"{germany_text} Germany", local=None)

    local_clock = _clock(local)
    if local.weekday() != in_germany.weekday():
        local_clock = f"{WEEKDAYS[local.weekday()]} {local_clock}"
    return Kickoff(germany=f"{germany_text} Germany", local=f"{local_clock} {label}")


def _same_wall_time(a: datetime, b: datetime) -> bool:
    return (a.weekday(), a.hour, a.minute) == (b.weekday(), b.hour, b.minute)
