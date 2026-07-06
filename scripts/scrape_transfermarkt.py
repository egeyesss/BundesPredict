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
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.players import ingest_squads
from bundespredict.data.transfermarkt import (
    LeagueClub,
    SquadPlayer,
    parse_league_page,
    parse_squad_page,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "tm_cache"
META_PATH = CACHE_DIR / "meta.json"

BASE_URL = "https://www.transfermarkt.com"
LEAGUE_URL = BASE_URL + "/bundesliga/startseite/wettbewerb/L1/plus/?saison_id={year}"
SQUAD_URL = BASE_URL + "/{slug}/kader/verein/{tm_id}/saison_id/{year}"

# Identify ourselves; hiding behind a browser UA is the impolite option.
USER_AGENT = "BundesPredict/0.1 (hobby Bundesliga model; contact: egeyesilyurtca@gmail.com)"
REQUEST_GAP_SECONDS = 3.0
MAX_ATTEMPTS = 3

FIRST_SEASON = 2019  # matches the ingested results history


def _current_season_start(today: datetime) -> int:
    """Bundesliga seasons start in August; before that we're in last year's."""
    return today.year if today.month >= 8 else today.year - 1


def _fetch(url: str) -> str:
    """One polite GET with retry/backoff; raises after the last attempt."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(REQUEST_GAP_SECONDS)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return str(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            wait = REQUEST_GAP_SECONDS * 2**attempt
            logger.warning("fetch failed (%s), retrying in %.0fs: %s", exc, wait, url)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _load_meta() -> dict[str, str]:
    if META_PATH.exists():
        return dict(json.loads(META_PATH.read_text()))
    return {}


def _save_meta(meta: dict[str, str]) -> None:
    META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True))


def _cache_page(name: str, url: str, meta: dict[str, str], *, refresh: bool) -> None:
    """Fetch ``url`` into the cache unless a copy exists and refresh is off."""
    path = CACHE_DIR / name
    if path.exists() and not refresh:
        logger.info("cached: %s", name)
        return
    logger.info("fetching %s", url)
    path.write_text(_fetch(url), encoding="utf-8")
    meta[name] = datetime.now(UTC).isoformat()


def fetch_all(current_year: int) -> None:
    """Fill the cache: every season's league page, current season's squads."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = _load_meta()

    for year in range(FIRST_SEASON, current_year + 1):
        # Historical league pages are frozen; only the current one moves.
        _cache_page(
            f"league_{year}.html",
            LEAGUE_URL.format(year=year),
            meta,
            refresh=(year == current_year),
        )
        _save_meta(meta)

    current_league = (CACHE_DIR / f"league_{current_year}.html").read_text(encoding="utf-8")
    for club in parse_league_page(current_league, current_year):
        _cache_page(
            f"squad_{club.tm_id}.html",
            SQUAD_URL.format(slug=club.slug, tm_id=club.tm_id, year=current_year),
            meta,
            refresh=True,
        )
        _save_meta(meta)


def ingest_cache(current_year: int) -> None:
    """Parse whatever the cache holds and upsert it into the database."""
    meta = _load_meta()

    clubs: list[LeagueClub] = []
    for year in range(FIRST_SEASON, current_year + 1):
        path = CACHE_DIR / f"league_{year}.html"
        if not path.exists():
            logger.warning("no cached league page for %d, skipping", year)
            continue
        clubs.extend(parse_league_page(path.read_text(encoding="utf-8"), year))

    current_season = f"{current_year % 100:02d}{(current_year + 1) % 100:02d}"
    current_clubs = {c.tm_id for c in clubs if c.season == current_season}
    squads: dict[int, list[SquadPlayer]] = {}
    squad_scraped_at: datetime | None = None
    for tm_id in sorted(current_clubs):
        name = f"squad_{tm_id}.html"
        path = CACHE_DIR / name
        if not path.exists():
            logger.warning("no cached squad page for club %d, skipping", tm_id)
            continue
        squads[tm_id] = parse_squad_page(path.read_text(encoding="utf-8"))
        if name in meta:
            fetched = datetime.fromisoformat(meta[name]).replace(tzinfo=None)
            squad_scraped_at = min(squad_scraped_at or fetched, fetched)

    scraped_at = squad_scraped_at or datetime.now(UTC).replace(tzinfo=None)
    engine = make_engine()
    with make_session_factory(engine)() as session:
        summary = ingest_squads(session, clubs, squads, scraped_at=scraped_at)
    print(
        f"Ingested: {summary.teams_linked} teams linked, "
        f"{summary.players_stored} players, {summary.squad_values_stored} squad values "
        f"(snapshot {scraped_at:%Y-%m-%d})."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="ingest from the existing cache without touching the network",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    current_year = _current_season_start(datetime.now())
    if not args.skip_fetch:
        fetch_all(current_year)
    ingest_cache(current_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
