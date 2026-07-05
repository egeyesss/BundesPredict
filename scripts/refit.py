"""Refresh the data and refit the serving model.

The offline training job: pull the current season's CSV, re-ingest (the upsert
refreshes corrected results and appends new ones), fit Dixon-Coles on the full
history with time decay, shrink low-history teams, and persist a versioned run
to ``model_runs``/``team_params``. The API serves whatever the latest persisted
run is — it never fits inside a request — so running this weekly (or after every
matchday) is what keeps predictions current.

Run it with the model extra installed::

    pip install -e ".[model]"
    python scripts/refit.py

``--skip-download`` trains on whatever is already in the database (useful
offline). By default the decay rate is the walk-forward-selected value from the
evaluation (xi = 0.004, ~173-day half-life); pass ``--select-xi`` to re-run the
selection on current data — worth doing occasionally, not every week.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.ingest import ingest_dir
from bundespredict.data.loader import load_dated_matches
from bundespredict.data.params_store import save_ratings
from bundespredict.model.dixon_coles import fit_dixon_coles
from bundespredict.model.shrinkage import shrink_ratings, team_match_counts
from bundespredict.model.time_decay import select_xi

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
SERVE_VERSION = "serve"
DEFAULT_XI = 0.004


def _current_season_start(today: date) -> int:
    """Bundesliga seasons start in August; before that we're in last year's."""
    return today.year if today.month >= 8 else today.year - 1


def _download_current_season(today: date) -> None:
    """Re-pull the in-progress season's CSV (idempotent script, forced refresh)."""
    year = _current_season_start(today)
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "download_seasons.py"),
        "--start",
        str(year),
        "--end",
        str(year),
        "--force",
    ]
    logger.info("downloading season %d/%d CSV...", year, year + 1)
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="train on the data already in the database",
    )
    parser.add_argument(
        "--select-xi",
        action="store_true",
        help="re-select the time-decay rate walk-forward instead of the default",
    )
    parser.add_argument(
        "--xi", type=float, default=None, help=f"decay rate override (default {DEFAULT_XI})"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    today = date.today()

    if not args.skip_download:
        _download_current_season(today)

    engine = make_engine()
    with make_session_factory(engine)() as session:
        if not args.skip_download:
            stats = ingest_dir(session, RAW_DIR)
            total = sum(s.matches_upserted for s in stats)
            logger.info("ingested %d files (%d matches upserted)", len(stats), total)

        dated = load_dated_matches(session)

        if args.xi is not None:
            xi = args.xi
        elif args.select_xi:
            sel = select_xi(
                dated.teams,
                dated.home_idx,
                dated.away_idx,
                dated.home_goals,
                dated.away_goals,
                dated.day_ordinal,
            )
            xi = sel.xi
            logger.info("selected xi=%.4f walk-forward", xi)
        else:
            xi = DEFAULT_XI

        data = dated.to_match_data(xi=xi, reference=today)
        logger.info("fitting Dixon-Coles on %d matches (xi=%.4f)...", len(dated), xi)
        ratings = fit_dixon_coles(data)
        ratings = shrink_ratings(ratings, team_match_counts(data))

        run_id = save_ratings(
            session,
            ratings,
            xi=xi,
            n_matches=len(dated),
            as_of_date=today,
            version=SERVE_VERSION,
            notes="scheduled refit on full history",
        )

    print(
        f"Refit done: run {run_id} on {len(dated)} matches "
        f"(rho={ratings.rho:.3f}, home_adv={ratings.home_adv:.3f}). Serving picks it up."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
