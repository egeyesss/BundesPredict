"""The rendered matchday mail: subject, preheader, inline-styled tables, footer and plain text."""

from __future__ import annotations

import html as htmllib
import re
from dataclasses import replace
from datetime import UTC, datetime

from notifications.matchday import (
    FixtureLine,
    LastMatchday,
    Matchday,
    Recipient,
    render_matchday_email,
)

SITE = "https://bundespredict.egeyesilyurt.ca"


def line(
    home: str, away: str, probs: tuple[float, float, float], xg: tuple[float, float], hour: int = 13
) -> FixtureLine:
    return FixtureLine(
        home_name=home,
        away_name=away,
        home_code=home[:3].upper(),
        away_code=away[:3].upper(),
        kickoff_utc=datetime(2026, 10, 17, hour, 30, tzinfo=UTC),
        probs=probs,
        xg=xg,
    )


LINES = [
    line("Frankfurt", "Köln", (0.5312, 0.2391, 0.2297), (1.92, 1.08), 18),
    line("Union Berlin", "Dortmund", (0.2618, 0.2544, 0.4838), (1.11, 1.74)),
    line("Bayern", "Leipzig", (0.6421, 0.1902, 0.1677), (2.61, 1.14), 16),
    line("Schalke", "Mainz", (0.3349, 0.3352, 0.3299), (1.18, 1.16)),
]
MATCHDAY = Matchday(season="2627", number=6, lines=LINES, last=None)
RECIPIENT = Recipient(
    first_name="Ege", timezone="America/Toronto", timezone_source="browser", token="TOKEN123"
)


def test_subject_names_the_strongest_favourite() -> None:
    assert (
        render_matchday_email(MATCHDAY, RECIPIENT).subject
        == "Matchday 6: Bayern 64% at home to Leipzig"
    )


def test_subject_for_an_away_favourite() -> None:
    lines = [line("Mainz", "Bayern", (0.12, 0.18, 0.70), (0.8, 2.4)), *LINES[:1]]

    subject = render_matchday_email(replace(MATCHDAY, lines=lines), RECIPIENT).subject

    assert subject == "Matchday 6: Bayern 70% away at Mainz"


def test_preheader_counts_fixtures_and_names_the_closest_call() -> None:
    rendered = render_matchday_email(MATCHDAY, RECIPIENT)

    assert rendered.preheader == (
        "Four fixtures, the model's odds for each, and the closest call of the weekend: "
        "Schalke v Mainz."
    )
    assert htmllib.unescape(rendered.preheader) in htmllib.unescape(rendered.html)


def test_html_is_tables_with_inline_styles_and_no_script_or_tracking() -> None:
    html = render_matchday_email(MATCHDAY, RECIPIENT).html

    assert "<script" not in html.lower()
    assert "<style" not in html.lower()
    assert "<link" not in html.lower()
    assert 'role="presentation"' in html
    assert not re.search(r"<img[^>]+(width|height)=\"[01]\"", html)


def test_every_link_points_at_the_site_or_is_the_contact_address() -> None:
    html = render_matchday_email(MATCHDAY, RECIPIENT).html

    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs
    assert all(
        h.startswith(f"{SITE}/") or h == "mailto:bundespredict@egeyesilyurt.ca" for h in hrefs
    )
    srcs = re.findall(r'src="([^"]+)"', html)
    assert srcs
    assert all(
        s.startswith(f"{SITE}/crests/png/") and s.endswith(("-48.png", "-96.png")) for s in srcs
    )


def test_unsubscribe_link_carries_the_token() -> None:
    rendered = render_matchday_email(MATCHDAY, RECIPIENT)

    assert f"{SITE}/email/unsubscribe?t=TOKEN123" in rendered.html
    assert f"{SITE}/email/unsubscribe?t=TOKEN123" in rendered.text


def test_odds_bars_use_solid_hex_colours_only() -> None:
    html = render_matchday_email(MATCHDAY, RECIPIENT).html

    assert "color-mix" not in html
    assert "rgba(" not in html
    assert "#22C55E" in html


def test_kickoffs_show_german_and_saved_timezone() -> None:
    rendered = render_matchday_email(MATCHDAY, RECIPIENT)

    assert "Sat 15:30 Germany" in rendered.html
    assert "09:30 Toronto" in rendered.html
    assert "Sat 15:30 Germany · 09:30 Toronto" in rendered.text


def test_unknown_timezone_falls_back_to_utc_and_says_so() -> None:
    rendered = render_matchday_email(MATCHDAY, replace(RECIPIENT, timezone=None))

    assert "13:30 UTC" in rendered.html
    assert "German time and UTC" in rendered.html


def test_footer_covers_casl_identification_reason_and_contact() -> None:
    html = render_matchday_email(MATCHDAY, RECIPIENT).html

    assert "Sent by BundesPredict" in html
    assert "L4B 0J4, Canada" in html
    assert "bundespredict@egeyesilyurt.ca" in html
    assert "Pro account" in html
    assert "Unsubscribe" in html
    assert "not affiliated with" in html


def test_a_greeting_uses_the_first_name_when_known() -> None:
    assert "Hi Ege," in render_matchday_email(MATCHDAY, RECIPIENT).text
    assert "Hi " not in render_matchday_email(MATCHDAY, replace(RECIPIENT, first_name="")).text


def test_the_plain_text_lists_every_fixture_with_its_odds() -> None:
    text = render_matchday_email(MATCHDAY, RECIPIENT).text

    assert "Bayern v Leipzig" in text
    assert "Bayern 64% | Draw 19% | Leipzig 17%" in text
    assert "xG 2.61 – 1.14" in text


def test_last_matchday_block_appears_only_with_data() -> None:
    assert "Last matchday" not in render_matchday_email(MATCHDAY, RECIPIENT).html

    with_last = replace(
        MATCHDAY, last=LastMatchday(number=5, favourites_won=6, played=9, rps=0.2041)
    )
    html = render_matchday_email(with_last, RECIPIENT).html

    assert "The favourite won 6 of 9" in html
    assert "0.204" in html


def test_html_escapes_names() -> None:
    lines = [line("A<b>", "B&C", (0.5, 0.3, 0.2), (1.0, 1.0))]

    html = render_matchday_email(replace(MATCHDAY, lines=lines), RECIPIENT).html

    assert "A<b>" not in html
    assert "B&amp;C" in html
