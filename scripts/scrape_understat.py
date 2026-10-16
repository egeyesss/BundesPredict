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
import logging
from pathlib import Path

from bundespredict.data.understat_scrape import (
    FIRST_SEASON,
    LAST_SEASON,
    fetch_season,
    scrape_seasons,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "understat_cache"


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

    years = [] if args.skip_fetch else args.seasons or list(range(FIRST_SEASON, LAST_SEASON + 1))
    scraped = scrape_seasons(
        CACHE_DIR, years, fetch=lambda year: fetch_season(year, headless=args.headless)
    )
    if scraped:
        logger.info("scraped: %s", ", ".join(f"{k}={v}" for k, v in sorted(scraped.items())))
    elif years:
        logger.warning("nothing cached; check the errors above")

    if not args.skip_ingest:
        _ingest_cache()


def _ingest_cache() -> None:
    """Backfill matches.home_xg/away_xg from the cache."""
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
