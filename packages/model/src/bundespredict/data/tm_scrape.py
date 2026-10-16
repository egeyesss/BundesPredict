"""Fetch Transfermarkt pages into an on-disk cache and read the cache back as dataclasses.

Politeness is the design constraint: an identifying User-Agent, one request every ~3 seconds,
retry with backoff on transient failures, and aggressive caching. Raw HTML lands in the cache
directory and the cache is the source of truth: reading never touches the network, so a
blocked or flaky scrape keeps serving the last snapshot. Historical league pages never change
and are fetched at most once; the current season's pages are refreshed on every run.

Two page types are fetched:

* league pages (one per season): club list, tm club ids, squad values (era-correct on
  historical pages, which is what the shrinkage prior needs)
* squad pages (current season only): per-player positions and market values

Writing the snapshot to a database is the caller's job.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .seasons import season_code
from .transfermarkt import LeagueClub, SquadPlayer, parse_league_page, parse_squad_page

logger = logging.getLogger(__name__)

BASE_URL = "https://www.transfermarkt.com"
LEAGUE_URL = BASE_URL + "/bundesliga/startseite/wettbewerb/L1/plus/?saison_id={year}"
SQUAD_URL = BASE_URL + "/{slug}/kader/verein/{tm_id}/saison_id/{year}"

# Identify ourselves; hiding behind a browser UA is the impolite option.
USER_AGENT = "BundesPredict/0.1 (hobby Bundesliga model; contact: egeyesilyurtca@gmail.com)"
REQUEST_GAP_SECONDS = 3.0
MAX_ATTEMPTS = 3

FIRST_SEASON = 2019  # matches the ingested results history

PageFetcher = Callable[[str], str]


class ScrapeBlocked(RuntimeError):
    """Transfermarkt refused to serve the page (its AWS WAF challenges datacenter IPs)."""


@dataclass(frozen=True)
class TransfermarktSnapshot:
    """Everything the cache holds, parsed. ``scraped_at`` is when the squads were fetched."""

    clubs: list[LeagueClub]
    squads: dict[int, list[SquadPlayer]]
    scraped_at: datetime


def polite_fetch(url: str) -> str:
    """One GET with a pause before each attempt and backoff between retries."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(REQUEST_GAP_SECONDS)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                # The WAF answers a challenge with 202 and an empty body instead of an error
                # status, so urlopen treats it as success; retrying never clears it.
                if response.headers.get("x-amzn-waf-action") or response.status == 202:
                    raise ScrapeBlocked(
                        f"Transfermarkt answered with a bot challenge for {url}; "
                        "run the scrape from a residential connection"
                    )
                return str(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            wait = REQUEST_GAP_SECONDS * 2**attempt
            logger.warning("fetch failed (%s), retrying in %.0fs: %s", exc, wait, url)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _meta_path(cache_dir: Path) -> Path:
    return cache_dir / "meta.json"


def _load_meta(cache_dir: Path) -> dict[str, str]:
    path = _meta_path(cache_dir)
    return dict(json.loads(path.read_text())) if path.exists() else {}


def _save_meta(cache_dir: Path, meta: dict[str, str]) -> None:
    _meta_path(cache_dir).write_text(json.dumps(meta, indent=2, sort_keys=True))


def _cache_page(
    cache_dir: Path, name: str, url: str, meta: dict[str, str], fetch: PageFetcher, *, refresh: bool
) -> None:
    path = cache_dir / name
    if path.exists() and not refresh:
        logger.info("cached: %s", name)
        return
    logger.info("fetching %s", url)
    html = fetch(url)
    if not html.strip():
        raise ScrapeBlocked(f"empty page for {url}; keeping the cached copy")
    path.write_text(html, encoding="utf-8")
    meta[name] = datetime.now(UTC).isoformat()


def fetch_all(cache_dir: Path, current_year: int, *, fetch: PageFetcher = polite_fetch) -> None:
    """Fill the cache: every season's league page, the current season's squads."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    meta = _load_meta(cache_dir)

    for year in range(FIRST_SEASON, current_year + 1):
        # Historical league pages are frozen; only the current one moves.
        _cache_page(
            cache_dir,
            f"league_{year}.html",
            LEAGUE_URL.format(year=year),
            meta,
            fetch,
            refresh=(year == current_year),
        )
        _save_meta(cache_dir, meta)

    current_league = (cache_dir / f"league_{current_year}.html").read_text(encoding="utf-8")
    for club in parse_league_page(current_league, current_year):
        _cache_page(
            cache_dir,
            f"squad_{club.tm_id}.html",
            SQUAD_URL.format(slug=club.slug, tm_id=club.tm_id, year=current_year),
            meta,
            fetch,
            refresh=True,
        )
        _save_meta(cache_dir, meta)


def read_cache(cache_dir: Path, current_year: int) -> TransfermarktSnapshot:
    """Parse whatever the cache holds. Missing pages are skipped with a warning.

    ``scraped_at`` is the oldest squad-page fetch time recorded in the cache metadata (the
    snapshot is only as fresh as its stalest page), or now when nothing was fetched yet.
    """
    meta = _load_meta(cache_dir)

    clubs: list[LeagueClub] = []
    for year in range(FIRST_SEASON, current_year + 1):
        path = cache_dir / f"league_{year}.html"
        if not path.exists():
            logger.warning("no cached league page for %d, skipping", year)
            continue
        clubs.extend(parse_league_page(path.read_text(encoding="utf-8"), year))

    current_clubs = {c.tm_id for c in clubs if c.season == season_code(current_year)}
    squads: dict[int, list[SquadPlayer]] = {}
    oldest_fetch: datetime | None = None
    for tm_id in sorted(current_clubs):
        name = f"squad_{tm_id}.html"
        path = cache_dir / name
        if not path.exists():
            logger.warning("no cached squad page for club %d, skipping", tm_id)
            continue
        squads[tm_id] = parse_squad_page(path.read_text(encoding="utf-8"))
        if name in meta:
            fetched = datetime.fromisoformat(meta[name])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=UTC)
            oldest_fetch = min(oldest_fetch or fetched, fetched)

    return TransfermarktSnapshot(
        clubs=clubs, squads=squads, scraped_at=oldest_fetch or datetime.now(UTC)
    )
