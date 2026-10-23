"""Kickoffs show German time plus the recipient's saved timezone, converted with IANA rules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from notifications.kickoff import format_kickoff


def kick(year: int, month: int, day: int, hour: int, minute: int, zone: str | None) -> str:
    return format_kickoff(datetime(year, month, day, hour, minute, tzinfo=UTC), zone).text


def test_shows_german_time_and_the_recipients_time() -> None:
    assert kick(2026, 10, 17, 13, 30, "America/Toronto") == "Sat 15:30 Germany · 09:30 Toronto"


def test_repeats_the_weekday_only_when_the_local_day_differs() -> None:
    assert kick(2026, 10, 17, 13, 30, "Asia/Tokyo") == "Sat 15:30 Germany · 22:30 Tokyo"
    assert kick(2026, 10, 17, 18, 30, "Asia/Tokyo") == "Sat 20:30 Germany · Sun 03:30 Tokyo"
    assert (
        kick(2026, 10, 17, 21, 30, "America/Los_Angeles") == "Sat 23:30 Germany · 14:30 Los Angeles"
    )
    assert (
        kick(2026, 10, 18, 1, 30, "America/Los_Angeles")
        == "Sun 03:30 Germany · Sat 18:30 Los Angeles"
    )


def test_shows_the_time_once_when_the_zones_agree() -> None:
    assert kick(2026, 10, 17, 13, 30, "Europe/Berlin") == "Sat 15:30 Germany"


@pytest.mark.parametrize("zone", [None, "", "Not/AZone"])
def test_falls_back_to_utc_when_the_zone_is_unknown(zone: str | None) -> None:
    assert kick(2026, 10, 17, 13, 30, zone) == "Sat 15:30 Germany · 13:30 UTC"


def test_europe_and_north_america_change_clocks_a_week_apart() -> None:
    # Europe fell back on 2026-10-25, North America does so on 2026-11-01.
    before_both = kick(2026, 10, 24, 13, 30, "America/Toronto")
    gap_week = kick(2026, 10, 31, 13, 30, "America/Toronto")
    after_both = kick(2026, 11, 7, 14, 30, "America/Toronto")

    assert before_both == "Sat 15:30 Germany · 09:30 Toronto"
    assert gap_week == "Sat 14:30 Germany · 09:30 Toronto"
    assert after_both == "Sat 15:30 Germany · 09:30 Toronto"


def test_gap_week_for_a_west_coast_recipient() -> None:
    assert (
        kick(2026, 10, 31, 13, 30, "America/Los_Angeles") == "Sat 14:30 Germany · 06:30 Los Angeles"
    )
    assert (
        kick(2026, 11, 7, 14, 30, "America/Los_Angeles") == "Sat 15:30 Germany · 06:30 Los Angeles"
    )


def test_rejects_a_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        format_kickoff(datetime(2026, 10, 17, 13, 30), "America/Toronto")
