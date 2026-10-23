"""Builds the weekly matchday email: what the model says, and one rendered message per reader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from django.conf import settings
from django.template.loader import render_to_string

from football.models import Fixture, Match
from football.repositories import SERVING_VERSION, latest_model_run, ratings_for, upcoming_fixtures
from track_record.models import FixturePrediction

from .kickoff import format_kickoff
from .odds import DisplayOdds, display_odds

CONTACT_EMAIL = "bundespredict@egeyesilyurt.ca"
MAX_LEAD = timedelta(days=5)

# Pre-mixed against the card surface #131316: email clients do not support color-mix().
SEGMENT_COLOURS = {
    "win": "#22C55E",
    "lose": "#D20515",
    "draw": "#71717A",
    "draw_lead": "#D4D4D8",
    "win_muted": "#1A4A2E",
    "lose_muted": "#56090F",
    "draw_muted": "#45454C",
}
COUNT_WORDS = (
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
)


@dataclass(frozen=True)
class FixtureLine:
    home_name: str
    away_name: str
    home_code: str | None
    away_code: str | None
    kickoff_utc: datetime
    probs: tuple[float, float, float]
    xg: tuple[float, float]


@dataclass(frozen=True)
class LastMatchday:
    number: int
    favourites_won: int
    played: int
    rps: float


@dataclass(frozen=True)
class Matchday:
    season: str
    number: int
    lines: list[FixtureLine]
    last: LastMatchday | None

    @property
    def campaign(self) -> str:
        return f"matchday-{self.season}-{self.number:02d}"


@dataclass(frozen=True)
class Recipient:
    first_name: str
    timezone: str | None
    timezone_source: str
    token: str


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    preheader: str
    html: str
    text: str
    one_click_url: str


def season_label(season: str) -> str:
    if len(season) == 4 and season.isdigit():
        century = "19" if int(season[:2]) >= 50 else "20"
        return f"{century}{season[:2]}/{season[2:]}"
    return season


def _ranked_probability_score(probs: tuple[float, float, float], outcome: int) -> float:
    actual = [1.0 if i == outcome else 0.0 for i in range(3)]
    first = probs[0] - actual[0]
    second = (probs[0] + probs[1]) - (actual[0] + actual[1])
    return (first**2 + second**2) / 2


def _last_matchday(season: str, number: int) -> LastMatchday | None:
    previous = list(
        Fixture.objects.filter(season=season, matchday=number - 1).select_related("home", "away")
    )
    if not previous:
        return None
    frozen = {p.fixture_id: p for p in FixturePrediction.objects.filter(fixture__in=previous)}
    won = 0
    scores: list[float] = []
    for fixture in previous:
        prediction = frozen.get(fixture.id)
        if prediction is None:
            return None
        day: date = fixture.kickoff_utc.date()
        match = Match.objects.filter(
            home=fixture.home,
            away=fixture.away,
            date__range=(day - timedelta(days=1), day + timedelta(days=1)),
        ).first()
        if match is None:
            return None
        outcome = (
            0
            if match.home_goals > match.away_goals
            else 2
            if match.home_goals < match.away_goals
            else 1
        )
        favourite = 0 if prediction.p_home >= prediction.p_away else 2
        won += outcome == favourite
        scores.append(
            _ranked_probability_score(
                (prediction.p_home, prediction.p_draw, prediction.p_away), outcome
            )
        )
    return LastMatchday(
        number=number - 1, favourites_won=won, played=len(scores), rps=sum(scores) / len(scores)
    )


def build_matchday(now: datetime) -> Matchday | None:
    """The coming matchday's fixtures with the model's odds, or None when none kicks off soon."""
    fixtures = [f for f in upcoming_fixtures("next_matchday", now) if f.kickoff_utc > now]
    if not fixtures or fixtures[0].kickoff_utc - now > MAX_LEAD:
        return None

    frozen = {p.fixture_id: p for p in FixturePrediction.objects.filter(fixture__in=fixtures)}
    run = latest_model_run(version=SERVING_VERSION)
    ratings = ratings_for(run) if run is not None else None

    lines: list[FixtureLine] = []
    for fixture in fixtures:
        prediction = frozen.get(fixture.id)
        if prediction is not None:
            probs = (prediction.p_home, prediction.p_draw, prediction.p_away)
            xg = (prediction.exp_home_goals, prediction.exp_away_goals)
        elif ratings is not None and {fixture.home.name, fixture.away.name} <= set(ratings.teams):
            markets = ratings.predict(fixture.home.name, fixture.away.name)
            probs = (markets.p_home, markets.p_draw, markets.p_away)
            xg = (markets.exp_home_goals, markets.exp_away_goals)
        else:
            continue
        lines.append(
            FixtureLine(
                home_name=fixture.home.short_name or fixture.home.name,
                away_name=fixture.away.short_name or fixture.away.name,
                home_code=fixture.home.code,
                away_code=fixture.away.code,
                kickoff_utc=fixture.kickoff_utc,
                probs=probs,
                xg=xg,
            )
        )
    if not lines:
        return None
    first = fixtures[0]
    return Matchday(
        season=first.season,
        number=first.matchday,
        lines=lines,
        last=_last_matchday(first.season, first.matchday),
    )


def _segment_colour(odds: DisplayOdds, index: int) -> str:
    role = odds.roles[index]
    leading = odds.lead == index
    if role == "draw":
        return SEGMENT_COLOURS["draw_lead" if leading else "draw_muted"]
    return SEGMENT_COLOURS[role if leading else f"{role}_muted"]


def _label_colour(odds: DisplayOdds, index: int) -> str:
    if odds.lead != index:
        return "#8B8B94"
    return "#4ADE80" if odds.roles[index] == "win" else "#F4F4F5"


def _crest(code: str | None) -> str | None:
    return f"{settings.PUBLIC_SITE_URL.rstrip('/')}/crests/png/{code}-48.png" if code else None


def _line_context(line: FixtureLine, timezone_name: str | None) -> dict[str, Any]:
    odds = display_odds(line.probs, line.xg)
    kickoff = format_kickoff(line.kickoff_utc, timezone_name)
    return {
        "home": line.home_name,
        "away": line.away_name,
        "home_crest": _crest(line.home_code),
        "away_crest": _crest(line.away_code),
        "kickoff": kickoff,
        "xg": f"xG {line.xg[0]:.2f} – {line.xg[1]:.2f}",
        "summary": " | ".join(
            [
                f"{line.home_name} {odds.text[0]}%",
                f"Draw {odds.text[1]}%",
                f"{line.away_name} {odds.text[2]}%",
            ]
        ),
        "segments": [
            {
                "width": max(3, round(line.probs[i] * 100)),
                "colour": _segment_colour(odds, i),
                "label_colour": _label_colour(odds, i),
                "bold": odds.lead == i,
                "percent": odds.text[i],
            }
            for i in range(3)
        ],
    }


def _headline(matchday: Matchday) -> tuple[str, str, str]:
    """The strongest favourite as (club, percent, where)."""
    strongest = max(matchday.lines, key=lambda line: max(line.probs[0], line.probs[2]))
    odds = display_odds(strongest.probs, strongest.xg)
    at_home = strongest.probs[0] >= strongest.probs[2]
    if at_home:
        return strongest.home_name, odds.text[0], f"at home to {strongest.away_name}"
    return strongest.away_name, odds.text[2], f"away at {strongest.home_name}"


def _closest(matchday: Matchday) -> tuple[FixtureLine, str]:
    closest = min(matchday.lines, key=lambda line: max(line.probs) - min(line.probs))
    spread = (max(closest.probs) - min(closest.probs)) * 100
    if spread < 1:
        return closest, "all three outcomes less than a point apart"
    return closest, f"all three outcomes within {round(spread)} points"


def render_matchday_email(matchday: Matchday, recipient: Recipient) -> RenderedEmail:
    favourite, percent, where = _headline(matchday)
    closest, spread_text = _closest(matchday)
    count = len(matchday.lines)
    word = COUNT_WORDS[count] if count < len(COUNT_WORDS) else str(count)
    subject = f"Matchday {matchday.number}: {favourite} {percent}% {where}"
    preheader = (
        f"{word} fixture{'' if count == 1 else 's'}, the model's odds for each, and the closest "
        f"call of the weekend: {closest.home_name} v {closest.away_name}."
    )
    site = settings.PUBLIC_SITE_URL.rstrip("/")
    context = {
        "site": site,
        "subject": subject,
        "preheader": preheader,
        "season": season_label(matchday.season),
        "number": matchday.number,
        "first_name": recipient.first_name,
        "favourite": favourite,
        "favourite_percent": percent,
        "favourite_where": where,
        "closest": f"{closest.home_name} v {closest.away_name}",
        "closest_note": spread_text,
        "fixtures": [_line_context(line, recipient.timezone) for line in matchday.lines],
        "last": matchday.last,
        "unsubscribe_url": f"{site}/email/unsubscribe?t={recipient.token}",
        "timezone": recipient.timezone,
        "timezone_from_browser": recipient.timezone_source == "browser",
        "mailing_address": settings.MAILING_ADDRESS,
        "contact_email": CONTACT_EMAIL,
    }
    return RenderedEmail(
        subject=subject,
        preheader=preheader,
        html=render_to_string("notifications/matchday_email.html", context),
        text=render_to_string("notifications/matchday_email.txt", context),
        one_click_url=f"{site}/api/v1/email/unsubscribe?token={recipient.token}",
    )
