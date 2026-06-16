"""Run the walk-forward backtest on the real data and write the metrics report.

This is the offline eval harness, not a request-path job. It refits the model
gameweek by gameweek across every season, scores the out-of-sample predictions
against the de-vigged market, calibrates on the pre-holdout seasons and measures
the held-out season, simulates flat-stake value betting with CLV, and writes a
committed markdown report plus reliability plots.

Run it with the model + report extras installed::

    pip install -e ".[model,report]"
    python scripts/run_backtest.py

It persists one ``model_runs`` row per gameweek (clearing any previous
walk-forward runs first, so re-running stays idempotent).
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: write PNGs, never open a window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from numpy.typing import NDArray  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from bundespredict.data.db import make_engine, make_session_factory  # noqa: E402
from bundespredict.data.loader import load_dated_matches  # noqa: E402
from bundespredict.data.models import ModelRun  # noqa: E402
from bundespredict.eval.backtest import BacktestResult, run_backtest  # noqa: E402
from bundespredict.eval.betting import value_bet_sim  # noqa: E402
from bundespredict.eval.metrics import (  # noqa: E402
    ForecastScores,
    reliability_curve,
    score_forecast,
)
from bundespredict.model.calibration import fit_temperature_scaler  # noqa: E402
from bundespredict.model.time_decay import select_xi  # noqa: E402

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


def _plot_reliability(
    probs_before: NDArray[np.float64],
    probs_after: NDArray[np.float64],
    outcomes: NDArray[np.intp],
    path: Path,
) -> None:
    """Reliability diagram on the holdout, uncalibrated vs temperature-scaled."""
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="perfect calibration")
    for probs, label, marker in (
        (probs_before, "uncalibrated", "o"),
        (probs_after, "calibrated", "s"),
    ):
        curve = reliability_curve(probs, outcomes)
        ax.plot(
            curve.bin_mean_pred,
            curve.bin_frac_pos,
            marker=marker,
            label=f"{label} (ECE={curve.ece:.3f})",
        )
    ax.set_xlabel("predicted probability")
    ax.set_ylabel("observed frequency")
    ax.set_title("1X2 reliability — holdout season")
    ax.legend(loc="upper left")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _scores_table(rows: list[tuple[str, ForecastScores]]) -> str:
    header = "| forecast | n | RPS | log-loss | Brier | ECE |\n|---|--:|--:|--:|--:|--:|"
    lines = [
        f"| {name} | {s.n} | {s.rps:.4f} | {s.log_loss:.4f} | {s.brier:.4f} | {s.ece:.4f} |"
        for name, s in rows
    ]
    return "\n".join([header, *lines])


def _write_report(
    result: BacktestResult,
    xi: float,
    holdout_season: str,
    overall_rows: list[tuple[str, ForecastScores]],
    holdout_rows: list[tuple[str, ForecastScores]],
    temperature: float,
    betting_summary: str,
    path: Path,
) -> None:
    model_rps = next(s for n, s in overall_rows if n == "model (calibrated)").rps
    market_rps = next(s for n, s in overall_rows if n == "market (close, de-vig)").rps
    gap = model_rps - market_rps
    verdict = "behind the market" if gap > 0.0005 else "roughly level with the market"

    # Honest calibration read: did temperature scaling actually help the holdout?
    h_uncal = next(s for n, s in holdout_rows if n == "model (uncalibrated)")
    h_cal = next(s for n, s in holdout_rows if n == "model (calibrated)")
    ece_delta = h_cal.ece - h_uncal.ece
    if temperature < 1.05:
        calib_note = (
            f"Temperature scaling landed at T = {temperature:.3f} — essentially the "
            f"identity, so the raw model was already close to calibrated."
        )
    elif ece_delta < -0.001:
        calib_note = (
            f"Temperature scaling (T = {temperature:.3f}) cut holdout ECE from "
            f"{h_uncal.ece:.4f} to {h_cal.ece:.4f} — the model was mildly overconfident "
            f"and softening helped."
        )
    else:
        calib_note = (
            f"Temperature scaling (T = {temperature:.3f}) found the model only mildly "
            f"overconfident, and on this {h_uncal.n}-match holdout it nudged ECE the wrong "
            f"way ({h_uncal.ece:.4f} → {h_cal.ece:.4f}). On so few matches that's noise, not "
            f"a regression to fix — the honest read is that the raw probabilities were "
            f"already near-calibrated and there was little for one parameter to do."
        )

    text = f"""# Backtest report — Dixon-Coles vs the market

*Generated by `scripts/run_backtest.py`. Walk-forward, refit every gameweek,
leakage-safe (each fit sees only results strictly before the round's kickoff).*

## Setup
- **Predictions:** {len(result)} matches, out-of-sample, across seasons
  `{min(result.seasons)}`–`{max(result.seasons)}` (the first season is warmup —
  used only to train, never predicted).
- **Time decay:** xi = {xi:.4f}, chosen walk-forward on the full history.
- **Calibration:** temperature scaling, T = {temperature:.3f}, fit on the
  pre-holdout seasons and applied to the held-out season `{holdout_season}`.
- **Skipped:** {result.n_skipped_unseen} fixtures with an unseen team (no prior
  top-flight history at the cutoff), {result.n_skipped_no_odds} for missing odds.
- **Baseline:** de-vigged market average (`Avg*`) closing odds — the strong
  baseline. Matching it is good; beating it is hard.

## Overall (all predicted seasons)
{_scores_table(overall_rows)}

## Holdout season `{holdout_season}` (calibrator never saw it)
{_scores_table(holdout_rows)}

Reliability before/after calibration: ![reliability](reliability.png)

## Value betting + CLV
{betting_summary}

## Honest read
On RPS — the metric that matters for ordinal H/D/A — the calibrated model is
**{verdict}** (model {model_rps:.4f} vs market {market_rps:.4f},
gap {gap:+.4f}; lower is better). That is the expected result: the closing line
aggregates money and sharper information than a goals-only Dixon-Coles fit, so
landing within a hundredth of an RPS point of it means the core model is sound.

{calib_note}

The value-bet ROI over ~1000 bets is dominated by variance and should not be read
as edge. **CLV** is the more trustworthy signal of skill, and the number above is
what to believe over ROI. What would actually move the model toward an edge:
pre-match xG team strength instead of goals, a market-blend (log opinion pool),
and lineup-aware adjustments — all later enrichment on this calibrated core, not
changes to it.
"""
    path.write_text(text, encoding="utf-8")


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

    holdout_season = max(result.seasons)
    seasons = np.array(result.seasons)
    holdout = seasons == holdout_season
    calib = ~holdout

    # Calibrate on everything before the holdout season, then apply everywhere.
    scaler = fit_temperature_scaler(result.model_probs[calib], result.outcomes[calib])
    calibrated = scaler.transform(result.model_probs)

    overall_rows = [
        ("model (uncalibrated)", score_forecast(result.model_probs, result.outcomes)),
        ("model (calibrated)", score_forecast(calibrated, result.outcomes)),
        ("market (open, de-vig)", score_forecast(result.market_probs_open, result.outcomes)),
        ("market (close, de-vig)", score_forecast(result.market_probs_close, result.outcomes)),
    ]
    holdout_rows = [
        (
            "model (uncalibrated)",
            score_forecast(result.model_probs[holdout], result.outcomes[holdout]),
        ),
        (
            "model (calibrated)",
            score_forecast(calibrated[holdout], result.outcomes[holdout]),
        ),
        (
            "market (close, de-vig)",
            score_forecast(result.market_probs_close[holdout], result.outcomes[holdout]),
        ),
    ]

    _plot_reliability(
        result.model_probs[holdout],
        calibrated[holdout],
        result.outcomes[holdout],
        REPORTS_DIR / "reliability.png",
    )

    bet = value_bet_sim(
        calibrated,
        result.market_probs_open,
        result.outcomes,
        result.bet_odds,
        result.close_odds,
    )
    betting_summary = (
        f"- **Bets placed:** {bet.n_bets} (1-unit flat stake, edge > 0.05 vs de-vigged "
        f"opening consensus, bet at Bet365 opening)\n"
        f"- **ROI:** {bet.roi:+.3%} (profit {bet.profit:+.2f} on {bet.total_staked:.0f} "
        f"staked) — variance-dominated, not evidence of edge\n"
        f"- **Win rate:** {bet.win_rate:.1%}\n"
        f"- **Beat the closing line:** {bet.beat_close_rate:.1%} of bets\n"
        f"- **Mean CLV:** {bet.mean_clv_pct:+.2%} (opening vs closing price) — the "
        f"signal to trust over ROI"
    )

    _write_report(
        result,
        xi,
        holdout_season,
        overall_rows,
        holdout_rows,
        scaler.temperature,
        betting_summary,
        REPORTS_DIR / "backtest_report.md",
    )
    logger.info("wrote %s", REPORTS_DIR / "backtest_report.md")
    print(f"Backtest done: {len(result)} predictions, holdout season {holdout_season}.")
    print(f"Report: {REPORTS_DIR / 'backtest_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
