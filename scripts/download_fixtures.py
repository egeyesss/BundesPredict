"""Refresh the upcoming-fixture schedule from OpenLigaDB.

Fetches the season's match list and mirrors the unplayed ones into the
``fixtures`` table (replace-per-season, so rescheduled kickoffs update and
played matches drop out). Run it alongside ``refit.py`` after a matchday, or
whenever the schedule for a new season is released.

    python scripts/download_fixtures.py            # current/upcoming season
    python scripts/download_fixtures.py --season 2026
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.fixtures import fetch_season_json, ingest_fixtures, parse_fixtures

logger = logging.getLogger(__name__)


def _default_season(today: date) -> int:
    """The season whose schedule matters now.

    From June on that's the season starting this calendar year (the summer gap
    belongs to the upcoming season — its schedule is what "next game" means);
    before June it's the season already running.
    """
    return today.year if today.month >= 6 else today.year - 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="season start year, e.g. 2026 for 2026/27 (default: inferred from today)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    season = args.season if args.season is not None else _default_season(date.today())
    logger.info("fetching Bundesliga %d/%d schedule from OpenLigaDB...", season, season + 1)
    payload = fetch_season_json(season)
    rows = parse_fixtures(payload, season)

    engine = make_engine()
    with make_session_factory(engine)() as session:
        stored = ingest_fixtures(session, rows)

    print(f"Stored {stored} upcoming fixtures for season {season}/{season + 1}.")
    if stored == 0:
        print("(The schedule may not be published yet, or every match is already played.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
