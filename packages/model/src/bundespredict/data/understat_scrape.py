"""Cache Understat per-match expected goals as raw JSON, one file per season.

Understat embeds each season's fixtures, including per-match xG for both sides, as a
``datesData`` JavaScript global on the league page. Plain HTTP gets a bot-stripped page and
the site sits behind Cloudflare, so the fetch drives a real local Chromium via Playwright:
from a normal residential machine the browser passes the gate and exposes the parsed global
directly, which is dumped verbatim into the cache.

The cache is the source of truth, like the Transfermarkt scrape: reading it (see
:func:`bundespredict.data.understat.load_cache`) never touches the network, so a blocked
scrape reuses the last snapshot. This is the one scraper that must run on a machine that can
reach Understat; CI and sandboxes are blocked.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .seasons import season_code

logger = logging.getLogger(__name__)

LEAGUE_URL = "https://understat.com/league/Bundesliga/{year}"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_GAP_SECONDS = 3.0
NAV_TIMEOUT_MS = 60_000

# The results history we model runs 2019/20 through 2025/26. Understat's league path takes
# the season's start year.
FIRST_SEASON = 2019
LAST_SEASON = 2025

SeasonFetcher = Callable[[int], list[dict[str, Any]]]


def cache_path(cache_dir: Path, start_year: int) -> Path:
    return cache_dir / f"bundesliga_{season_code(start_year)}.json"


def fetch_season(start_year: int, *, headless: bool) -> list[dict[str, Any]]:
    """Load one league season page and return its ``datesData`` array.

    Playwright is imported lazily so the module loads without it; the fetch itself needs a
    browser that can reach Understat.
    """
    from playwright.sync_api import sync_playwright

    url = LEAGUE_URL.format(year=start_year)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=USER_AGENT)
        page.set_default_timeout(NAV_TIMEOUT_MS)
        page.goto(url, wait_until="domcontentloaded")
        # Waiting for the data global is also what clears any Cloudflare interstitial.
        page.wait_for_function("() => typeof datesData !== 'undefined' && datesData.length > 0")
        # Stringify in the page so the JS Date fields serialize to ISO strings instead of
        # Playwright coercing them to Python datetimes.
        raw = page.evaluate("() => JSON.stringify(datesData)")
        browser.close()
    return list(json.loads(raw))


def _update_meta(cache_dir: Path, scraped: dict[str, int]) -> None:
    meta_path = cache_dir / "meta.json"
    meta: dict[str, Any] = dict(json.loads(meta_path.read_text())) if meta_path.exists() else {}
    now = datetime.now(UTC).isoformat()
    for code, n in scraped.items():
        meta[code] = {"scraped_at": now, "matches": n}
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True))


def scrape_seasons(
    cache_dir: Path,
    years: list[int],
    *,
    fetch: SeasonFetcher,
    pause: float = REQUEST_GAP_SECONDS,
) -> dict[str, int]:
    """Fetch each season into the cache; returns ``{season code: matches}`` for those that worked.

    A season that fails to load is logged and skipped, so one blocked page does not lose the
    others.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    scraped: dict[str, int] = {}
    for i, year in enumerate(years):
        if i:
            time.sleep(pause)
        code = season_code(year)
        logger.info("fetching Bundesliga %s (%s)...", year, code)
        try:
            data = fetch(year)
        except Exception:
            logger.exception(
                "failed to fetch %s; if this is a Cloudflare block, re-run without "
                "--headless so a real browser window can pass the check",
                year,
            )
            continue
        cache_path(cache_dir, year).write_text(json.dumps(data, ensure_ascii=False))
        scraped[code] = len(data)
        logger.info("  cached %d matches -> %s", len(data), cache_path(cache_dir, year).name)
    if scraped:
        _update_meta(cache_dir, scraped)
    return scraped
