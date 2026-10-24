import type { TrackRecord } from "@/lib/api/types";

import { ChartCard, LINE_LEGEND, Legend, ReliabilityChart, ReliabilityTable, RpsLineChart, RpsLineTable } from "./charts";
import { formatDay, isShortRecord, percent, scoredMatchdays, score } from "./format";
import { MatchdayList } from "./MatchdayList";
import { NewsEdge } from "./NewsEdge";
import { Tiles } from "./Tiles";

function EmptyLive({ record, onSeeBacktest }: { record: TrackRecord; onSeeBacktest: () => void }) {
  const { since } = record.live;
  return (
    <div className="grid max-w-[720px] gap-2.5 rounded-xl border border-dashed border-[#3a3a42] p-7">
      <span className="font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase">{since ? `Live since ${formatDay(since)}` : "Live record"}</span>
      <h2 className="font-display text-[clamp(28px,4vw,38px)] leading-none font-bold text-balance">No matchday scored yet</h2>
      <p className="text-bp-text-muted">
        Predictions for every fixture are frozen 48 hours before kickoff, before any team news, and can&apos;t be edited after that. Once a match has been played and its result is in, it is scored and shows up here, usually the next morning.
      </p>
      <p className="text-bp-text-muted">Until then, the backtest shows how the same model did on 1,827 past matches.</p>
      <div>
        <button type="button" onClick={onSeeBacktest} className="touch-target rounded-md border border-bp-border bg-bp-surface-2 px-2.5 py-1.5 font-mono text-xs font-medium text-bp-text-muted hover:text-bp-text">
          See the backtest
        </button>
      </div>
    </div>
  );
}

export function LivePanel({ record, onSeeBacktest }: { record: TrackRecord; onSeeBacktest: () => void }) {
  const { live } = record;
  if (!live.model) {
    return (
      <>
        <EmptyLive record={record} onSeeBacktest={onSeeBacktest} />
        <NewsEdge edge={record.news_edge} />
      </>
    );
  }

  const matchdays = scoredMatchdays(record.matchdays);
  const hits = Math.round((live.model.hit_rate ?? 0) * live.model.n_fixtures);
  const noMarket = live.bookmaker !== null && live.bookmaker.n_fixtures < live.model.n_fixtures;

  return (
    <>
      {isShortRecord(live) && (
        <p className="w-fit max-w-full rounded-lg border border-bp-border px-2 py-0.5 font-mono text-[11px] leading-normal text-bp-text-muted">
          Only {live.model.n_fixtures} {live.model.n_fixtures === 1 ? "match" : "matches"} scored so far. A record this short moves a lot with every result.
        </p>
      )}
      <Tiles
        tiles={[
          {
            label: "Matches scored",
            value: String(live.model.n_fixtures),
            context: live.since ? `Live since ${formatDay(live.since)}` : live.label,
          },
          {
            label: "Model RPS",
            value: score(live.model.rps),
            context: (
              <>
                closing market <b>{live.bookmaker ? score(live.bookmaker.rps) : "n/a"}</b>
                {noMarket && live.bookmaker ? ` (${live.bookmaker.n_fixtures} matches)` : ""} · base rate <b>{live.base_rate ? score(live.base_rate.rps) : "n/a"}</b>
              </>
            ),
          },
          {
            label: "Log loss",
            value: score(live.model.log_loss),
            context: (
              <>
                closing market <b>{live.bookmaker ? score(live.bookmaker.log_loss) : "n/a"}</b> · base rate <b>{live.base_rate ? score(live.base_rate.log_loss) : "n/a"}</b>
              </>
            ),
          },
          {
            label: "Favourite won",
            value: percent(live.model.hit_rate ?? 0),
            context: `${hits} of ${live.model.n_fixtures} matches`,
          },
        ]}
      />

      <ChartCard
        title="Average RPS per matchday"
        description="Lower is better. The base rate always predicts the league's long-run split (44% home, 25% draw, 31% away), so beating it is the minimum bar."
        legend={<Legend items={LINE_LEGEND} />}
        chart={<RpsLineChart rows={matchdays} />}
        table={<RpsLineTable rows={matchdays} />}
      />

      {record.calibration.length > 0 && (
        <ChartCard
          title="When it says 40%, does it happen 40% of the time?"
          description="Every home, draw and away probability scored this season, grouped into bins. Points on the dashed line are perfectly calibrated."
          chart={
            <div className="grid items-start gap-6 min-[900px]:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
              <ReliabilityChart bins={record.calibration} />
              <p className="max-w-[48ch] text-sm text-bp-text-muted">
                A point above the dashed line means that outcome happened more often than the model said; below means less often. Hover a point to see how many predictions sit in it.
              </p>
            </div>
          }
          table={<ReliabilityTable bins={record.calibration} />}
          note={isShortRecord(live) ? <p className="font-mono text-[11px] text-bp-text-muted">With this few matches most bins hold only a handful of predictions, so read the shape loosely.</p> : undefined}
        />
      )}

      <NewsEdge edge={record.news_edge} />

      <h2 className="font-display text-[clamp(28px,4vw,38px)] leading-none font-bold">Every match</h2>
      <MatchdayList rows={record.matchdays} />
      <p className="max-w-[76ch] text-sm text-bp-text-muted">
        <b className="font-medium text-bp-text">Reading a row:</b> the bar is the frozen prediction, the small marker shows what actually happened, and the match RPS is how far off the prediction was (0 is perfect).
      </p>
    </>
  );
}
