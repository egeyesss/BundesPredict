"""Run the walk-forward backtest on the real data and write the metrics report.

This is the offline eval harness, not a request-path job. It refits the model
gameweek by gameweek across every season, scores the out-of-sample predictions
against the de-vigged market, calibrates on the pre-holdout seasons and measures
the held-out season, simulates flat-stake value betting with CLV, and writes a
committed markdown report plus reliability plots.

Run it with the report extra (matplotlib) added to the workspace install::

    uv run --package bundespredict --extra report python scripts/run_backtest.py

It persists one ``model_runs`` row per gameweek (clearing any previous
walk-forward runs first, so re-running stays idempotent).
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete

from bundespredict.data.db import make_engine, make_session_factory
from bundespredict.data.loader import load_dated_matches
from bundespredict.data.models import ModelRun
from bundespredict.eval.backtest import run_backtest
from bundespredict.eval.report import build_report
from bundespredict.model.time_decay import select_xi

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
WALK_FORWARD_VERSION = "walk-forward"


def _choose_xi() -> float:
    """Pick the decay rate walk-forward on the full history (the leakage-safe way)."""
    engine = make_engine()
    with make_session_factory(engine)() as session:
        dated = load_dated_matches(session)
    sel = select_xi(
        dated.teams,
        dated.home_idx,
        dated.away_idx,
        dated.home_goals,
        dated.away_goals,
        dated.day_ordinal,
    )
    logger.info("selected xi=%.4f (mean holdout LL=%.4f)", sel.xi, sel.holdout_log_likelihood)
    return sel.xi


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    REPORTS_DIR.mkdir(exist_ok=True)

    xi = _choose_xi()

    engine = make_engine()
    with make_session_factory(engine)() as session:
        # Idempotent: drop previous walk-forward runs (cascades to team_params).
        session.execute(delete(ModelRun).where(ModelRun.version == WALK_FORWARD_VERSION))
        session.commit()

        logger.info("running walk-forward backtest (this refits per gameweek)...")
        result = run_backtest(session, xi=xi, persist=True)

        # Same walk-forward, but with the pre-match rolling-xG offset switched on,
        # to measure whether xG earns its place. Not persisted: serving stays
        # goals-only unless this beats it out of sample.
        logger.info("running the pre-match xG variant for comparison...")
        xg_result = run_backtest(session, xi=xi, persist=False, use_xg=True)

    summary = build_report(result, xg_result, xi=xi, reports_dir=REPORTS_DIR)
    logger.info("wrote %s", summary.report_path)
    print(f"Backtest done: {len(result)} predictions, holdout season {summary.holdout_season}.")
    print(f"Report: {summary.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
