"""Scrape Transfermarkt squads + market values into the cache, then ingest.

Politeness is the design constraint: an identifying User-Agent, one request
every ~3 seconds, retry with backoff on transient failures, and aggressive
caching. Raw HTML lands in ``data/tm_cache/`` (gitignored) and **the cache is
the source of truth**: ingest only ever reads cached files, so a blocked or
flaky scrape can never break the app — it just keeps serving the last
snapshot. Historical league pages never change and are fetched at most once;
current-season pages are refreshed on every run (weekly, alongside the refit
job).

Two page types are fetched:

* league pages (one per season) -> club list, tm club ids, squad values
  (era-correct on historical pages — that's what the shrinkage prior needs)
* squad pages (current season only) -> per-player positions + market values

Run it with the base install::

    python scripts/scrape_transfermarkt.py                  # fetch + ingest
    python scripts/scrape_transfermarkt.py --skip-fetch     # ingest cache only
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.players import ingest_squads
from bundespredict.data.seasons import results_season_start
from bundespredict.data.tm_scrape import fetch_all, read_cache

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "tm_cache"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="ingest from the existing cache without touching the network",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    current_year = results_season_start(datetime.now(UTC).date())
    if not args.skip_fetch:
        fetch_all(CACHE_DIR, current_year)

    snapshot = read_cache(CACHE_DIR, current_year)
    # The legacy columns are timezone-naive UTC.
    scraped_at = snapshot.scraped_at.astimezone(UTC).replace(tzinfo=None)
    engine = make_engine()
    with make_session_factory(engine)() as session:
        summary = ingest_squads(session, snapshot.clubs, snapshot.squads, scraped_at=scraped_at)
    print(
        f"Ingested: {summary.teams_linked} teams linked, "
        f"{summary.players_stored} players, {summary.squad_values_stored} squad values "
        f"(snapshot {scraped_at:%Y-%m-%d})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
