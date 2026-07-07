"""Cache Understat per-match expected-goals into ``data/understat_cache/``.

Understat embeds each season's fixtures — including per-match xG for both sides —
as a ``datesData`` JavaScript global on the league page. Plain HTTP gets a
bot-stripped page (the data global is absent) and the site sits behind
Cloudflare, so this scraper drives a **real local Chromium via Playwright**:
from a normal residential machine the browser passes the gate and exposes the
parsed global directly (``window.datesData``), which we dump verbatim to the
cache.

The cache is the source of truth, exactly like the Transfermarkt scrape: ingest
reads the cached JSON, never the network, so a blocked or flaky scrape can never
break the model refit — it just reuses the last snapshot. Historical season
pages never change; the current season is refreshed on each run.

This is the one piece that must run on a machine that can reach Understat (CI and
sandboxes are blocked). It has no import-time dependency on the rest of the
package, so it runs anywhere Playwright is installed::

    pip install playwright && playwright install chromium
    python scripts/scrape_understat.py                 # all seasons, headed
    python scripts/scrape_understat.py --headless      # try headless first
    python scripts/scrape_understat.py --seasons 2025  # just the current one
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "understat_cache"
META_PATH = CACHE_DIR / "meta.json"

LEAGUE_URL = "https://understat.com/league/Bundesliga/{year}"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_GAP_SECONDS = 3.0
NAV_TIMEOUT_MS = 60_000

# The results history we model runs 2019/20 through 2025/26. Understat's league
# path takes the season's start year.
FIRST_SEASON = 2019
LAST_SEASON = 2025


def season_code(start_year: int) -> str:
    """2019 -> "1920", matching the season codes used for matches."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def cache_path(start_year: int) -> Path:
    return CACHE_DIR / f"bundesliga_{season_code(start_year)}.json"


def fetch_season(start_year: int, *, headless: bool) -> list[dict[str, Any]]:
    """Load one league season page and return its ``datesData`` array.

    Playwright is imported lazily so the module loads without it (e.g. for
    ``--help``); the fetch itself needs a browser that can reach Understat.
    """
    from playwright.sync_api import sync_playwright

    url = LEAGUE_URL.format(year=start_year)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=USER_AGENT)
        page.set_default_timeout(NAV_TIMEOUT_MS)
        page.goto(url, wait_until="domcontentloaded")
        # Wait for the data global to exist — this is also what clears any
        # Cloudflare interstitial (the real page only defines it once through).
        page.wait_for_function("() => typeof datesData !== 'undefined' && datesData.length > 0")
        # Stringify in the page so the JS Date fields serialize to ISO strings,
        # rather than letting Playwright coerce them to Python datetimes we'd have
        # to special-case. The cache then holds Understat's own JSON verbatim.
        raw = page.evaluate("() => JSON.stringify(datesData)")
        browser.close()
    return list(json.loads(raw))


def _write_cache(start_year: int, data: list[dict[str, Any]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(start_year).write_text(json.dumps(data, ensure_ascii=False))


def _update_meta(scraped: dict[str, int]) -> None:
    meta: dict[str, Any] = {}
    if META_PATH.exists():
        meta = dict(json.loads(META_PATH.read_text()))
    now = datetime.now(UTC).isoformat()
    for code, n in scraped.items():
        meta[code] = {"scraped_at": now, "matches": n}
    META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache Understat Bundesliga xG by season.")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="*",
        help=f"season start years (default {FIRST_SEASON}..{LAST_SEASON})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run Chromium headless (try it; fall back to headed if Cloudflare blocks)",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="don't scrape; ingest whatever is already cached",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="only cache the pages; don't backfill the matches table",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    years = args.seasons or list(range(FIRST_SEASON, LAST_SEASON + 1))
    if args.skip_fetch:
        years = []
    scraped: dict[str, int] = {}
    for i, year in enumerate(years):
        if i:
            time.sleep(REQUEST_GAP_SECONDS)
        code = season_code(year)
        logger.info("fetching Bundesliga %s (%s)...", year, code)
        try:
            data = fetch_season(year, headless=args.headless)
        except Exception:
            logger.exception(
                "failed to fetch %s — if this is a Cloudflare block, re-run without "
                "--headless so a real browser window can pass the check",
                year,
            )
            continue
        _write_cache(year, data)
        scraped[code] = len(data)
        logger.info("  cached %d matches -> %s", len(data), cache_path(year).name)

    if scraped:
        _update_meta(scraped)
        logger.info("scraped: %s", ", ".join(f"{k}={v}" for k, v in sorted(scraped.items())))
    elif years:
        logger.warning("nothing cached — check the errors above")

    if not args.skip_ingest:
        _ingest_cache()


def _ingest_cache() -> None:
    """Backfill matches.home_xg/away_xg from the cache (imports the package lazily)."""
    from bundespredict.data.db import make_engine, make_session_factory
    from bundespredict.data.understat import ingest_understat, load_cache

    if not CACHE_DIR.exists() or not any(CACHE_DIR.glob("bundesliga_*.json")):
        logger.warning("no cache to ingest at %s", CACHE_DIR)
        return
    with make_session_factory(make_engine())() as session:
        stats = ingest_understat(session, load_cache(CACHE_DIR))
    logger.info(
        "ingested: %d seasons, %d parsed, %d matched, %d unmatched",
        stats.seasons,
        stats.parsed,
        stats.matched,
        stats.unmatched,
    )


if __name__ == "__main__":
    main()
