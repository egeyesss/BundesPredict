"use client";

import { useState } from "react";

import type { Markets } from "@/lib/api/types";
import { formatMarketChange, marketRows } from "@/lib/chat/markets";
import { cn } from "@/lib/utils";

import { ScoreHeatmap } from "./ScoreHeatmap";

type View = "news" | "model";

type MoreMarketsProps = {
  home: string;
  away: string;
  baseline: Markets;
  /** Present when the agent applied news; without it there is nothing to compare. */
  adjusted: Markets | null;
};

const percent0 = (probability: number) => `${(probability * 100).toFixed(0)}%`;
const goals = (markets: Markets) => `${markets.exp_home_goals.toFixed(2)} – ${markets.exp_away_goals.toFixed(2)}`;

/** The scoreline heatmap, the goal markets and the likeliest scores, all read from the same score grid. */
export function MoreMarkets({ home, away, baseline, adjusted }: MoreMarketsProps) {
  const [view, setView] = useState<View>(adjusted ? "news" : "model");
  const comparing = adjusted !== null && view === "news";
  const shown = comparing ? adjusted : baseline;
  const rows = marketRows(shown, baseline, home, away);
  const likeliest = shown.top_scores[0];

  return (
    <details open className="group border-t border-bp-border pt-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded text-sm font-medium [&::-webkit-details-marker]:hidden">
        <span>More markets and scorelines</span>
        <span aria-hidden="true" className="font-mono text-xs text-bp-text-muted transition-transform group-open:rotate-180">
          ▾
        </span>
      </summary>

      <div className="grid gap-[18px] pt-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          {adjusted ? (
            <div role="group" aria-label="Show odds" className="inline-flex gap-0.5 rounded-full border border-bp-border bg-bp-bg p-[3px]">
              {(
                [
                  ["news", "With your news"],
                  ["model", "Model only"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={view === value}
                  onClick={() => setView(value)}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-[13px] whitespace-nowrap text-bp-text-muted",
                    view === value && "bg-bp-text font-semibold text-bp-bg",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <span />
          )}
          <span className="text-sm text-bp-text-muted">
            Most likely{" "}
            <b className="mx-1 font-display text-[22px] leading-none font-bold text-bp-text tabular-nums">
              {likeliest.home}–{likeliest.away}
            </b>
            {percent0(likeliest.p)}
          </span>
        </div>

        <div className="grid items-start gap-6 min-[700px]:grid-cols-[minmax(0,290px)_minmax(0,1fr)]">
          <ScoreHeatmap
            home={home}
            away={away}
            markets={shown}
            label={comparing ? "with your news" : "model only"}
            other={comparing ? { label: "model only", markets: baseline } : undefined}
          />

          <div className="grid min-w-0 content-start gap-2.5">
            <h3 className="font-display text-[17px] leading-tight font-semibold tracking-[0.02em]">Markets</h3>
            <div role="table" aria-label="Goal markets" className="grid gap-0.5">
              <div role="row" className={cn("grid gap-2 pb-2 font-mono text-[10px] tracking-wider text-bp-text-muted uppercase", comparing ? "grid-cols-[minmax(0,1fr)_46px_46px_80px]" : "grid-cols-[minmax(0,1fr)_54px]")}>
                <span role="columnheader">Market</span>
                {comparing ? (
                  <>
                    <span role="columnheader" className="text-right">News</span>
                    <span role="columnheader" className="text-right">Model</span>
                    <span role="columnheader" className="text-right">Change</span>
                  </>
                ) : (
                  <span role="columnheader" className="text-right">Model</span>
                )}
              </div>
              {rows.map((row) => (
                <div
                  key={row.name}
                  role="row"
                  className={cn(
                    "grid items-center gap-2 border-t border-bp-border py-2 text-sm",
                    comparing ? "grid-cols-[minmax(0,1fr)_46px_46px_80px]" : "grid-cols-[minmax(0,1fr)_54px]",
                  )}
                >
                  <span role="rowheader" className="min-w-0">
                    {row.name}
                    {row.sub && <small className="block text-xs text-bp-text-muted">{row.sub}</small>}
                  </span>
                  <span role="cell" className="text-right font-mono text-[13px] font-medium text-bp-text">
                    {percent0(row.now)}
                  </span>
                  {comparing && (
                    <>
                      <span role="cell" className="text-right font-mono text-[13px] text-bp-text-muted">
                        {percent0(row.before)}
                      </span>
                      <span role="cell" className="text-right font-mono text-xs whitespace-nowrap text-bp-text-muted">
                        {formatMarketChange(row.now, row.before)}
                      </span>
                    </>
                  )}
                </div>
              ))}
            </div>
            <p className="pt-1 font-mono text-xs text-bp-text-muted">
              Expected goals {home}–{away}: <b className="font-medium text-bp-text">{goals(shown)}</b>
              {comparing && <>, {goals(baseline)} model only</>}
            </p>

            <h3 className="mt-1.5 font-display text-[17px] leading-tight font-semibold tracking-[0.02em]">Most likely scores</h3>
            <ul className="flex list-none flex-wrap gap-1.5 p-0">
              {shown.top_scores.slice(0, 5).map((score) => (
                <li key={`${score.home}-${score.away}`} className="rounded-full border border-bp-border px-2.5 py-1 font-mono text-xs font-medium text-bp-text-muted">
                  <b className="mr-1.5 font-semibold text-bp-text">
                    {score.home}–{score.away}
                  </b>
                  {(score.p * 100).toFixed(1)}%
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="text-xs text-bp-text-muted">
          Every number here comes from the same score grid, so the markets can never disagree with each other or with the win, draw and loss odds above.
        </p>
      </div>
    </details>
  );
}
