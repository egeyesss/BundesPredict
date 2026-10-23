import type { TrackRecord } from "@/lib/api/types";

import { ChartCard, DOT_LEGEND, DotPlot, DotTable, Legend } from "./charts";
import { score } from "./format";
import { Tiles } from "./Tiles";

const REPORT_URL = "https://github.com/egeyesss/BundesPredict/blob/main/reports/backtest_report.md";

const FINDINGS = [
  {
    title: "Behind the market, by a little",
    body: "The closing line scores 0.1967 to the model's 0.2045. Bookmakers price in money and team news the goals-only model never sees, so being 0.008 behind is the expected result for a sound model.",
  },
  {
    title: "No edge over the opening line",
    body: "A blend of model and opening odds put all its weight on the odds. The model carries no information the opening line doesn't already have. That weight is re-checked after every model change.",
  },
  {
    title: "Pre-match xG didn't help",
    body: "Adding rolling pre-match xG improved the fit on training data but made out-of-sample RPS worse (0.2069 vs 0.2046), so it isn't used for serving.",
  },
];

export function BacktestPanel({ period }: { period: TrackRecord["backtest"] }) {
  const { model, bookmaker } = period;
  if (!model || !bookmaker) return null;
  const rows = period.forecasters.map((item) => ({ key: item.key, label: item.label, value: item.rps, kind: item.kind, serving: item.serving }));

  return (
    <>
      <Tiles
        tiles={[
          { label: "Matches predicted", value: model.n_fixtures.toLocaleString("en-US"), context: "2021/22 to 2025/26, refit every gameweek" },
          { label: "Model RPS", value: score(model.rps), context: <>closing market <b>{score(bookmaker.rps)}</b></> },
          { label: "Log loss", value: score(model.log_loss), context: <>closing market <b>{score(bookmaker.log_loss)}</b></> },
          { label: "Calibration error", value: score(period.calibration_error ?? 0), context: "ECE, lower is better" },
        ]}
      />
      <ChartCard
        title="Ranked probability score by forecaster"
        description={`All ${model.n_fixtures.toLocaleString("en-US")} out-of-sample matches. Lower is better. The axis is zoomed in: the whole spread is under 0.011.`}
        legend={<Legend items={DOT_LEGEND} />}
        chart={<DotPlot rows={rows} />}
        table={<DotTable rows={rows} />}
      />
      <div className="grid grid-cols-3 gap-3 max-[900px]:grid-cols-1">
        {FINDINGS.map((finding) => (
          <div key={finding.title} className="grid content-start gap-2 border-t-2 border-bp-border pt-3.5">
            <h3 className="font-display text-xl leading-tight font-semibold tracking-[0.02em]">{finding.title}</h3>
            <p className="text-sm text-bp-text-muted">{finding.body}</p>
          </div>
        ))}
      </div>
      <div className="grid max-w-[76ch] gap-2 text-sm text-bp-text-muted">
        <h3 className="font-display text-xl leading-tight font-semibold tracking-[0.02em] text-bp-text">How the backtest works</h3>
        <p>
          <b className="font-medium text-bp-text">Walk-forward.</b> Before each gameweek the model is refit on results strictly before that round&apos;s kickoff, then predicts the round. Nothing from the future leaks in.
        </p>
        <p>
          <b className="font-medium text-bp-text">Scored with RPS.</b> The ranked probability score treats home, draw and away as ordered, so calling a draw when the home side wins costs less than calling an away win.
        </p>
        <p>
          <a href={REPORT_URL} className="border-b border-bp-border font-medium text-bp-text hover:border-bp-text">
            Read the full backtest report on GitHub →
          </a>
        </p>
      </div>
    </>
  );
}
