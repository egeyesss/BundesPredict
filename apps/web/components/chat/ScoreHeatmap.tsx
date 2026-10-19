"use client";

import { useState } from "react";

import type { Markets } from "@/lib/api/types";
import { HEATMAP_SIZE, heatShade, scoreGrid } from "@/lib/chat/markets";
import { cn } from "@/lib/utils";

const LABEL_THRESHOLD = 0.05;
const GOAL_LEVELS = Array.from({ length: HEATMAP_SIZE }, (_, goals) => goals);
const percent = (probability: number, digits = 1) => `${(probability * 100).toFixed(digits)}%`;

export type ScoreHeatmapProps = {
  home: string;
  away: string;
  markets: Markets;
  /** The same grid from the other view, so a hovered cell can show both numbers. */
  other?: { label: string; markets: Markets };
  label?: string;
  className?: string;
};

type Hover = { home: number; away: number; left: number; top: number };

/** Every scoreline from 0-0 to 5-5 on one neutral ramp, so it never borrows the win and lose colours. */
export function ScoreHeatmap({ home, away, markets, other, label = "this view", className }: ScoreHeatmapProps) {
  const [showTable, setShowTable] = useState(false);
  const [hover, setHover] = useState<Hover | null>(null);

  const grid = scoreGrid(markets);
  const otherGrid = other ? scoreGrid(other.markets) : null;
  const strongest = Math.max(...grid.flat());
  const likeliest = markets.top_scores[0];
  const summary = `Scoreline probabilities, most likely ${likeliest.home}–${likeliest.away} at ${percent(likeliest.p)}`;

  function track(event: React.PointerEvent<HTMLDivElement>) {
    const cell = (event.target as HTMLElement).closest<HTMLElement>("[data-cell]");
    if (!cell) return setHover(null);
    const container = event.currentTarget.getBoundingClientRect();
    const box = cell.getBoundingClientRect();
    setHover({
      home: Number(cell.dataset.home),
      away: Number(cell.dataset.away),
      left: box.left - container.left + box.width + 6,
      top: box.top - container.top,
    });
  }

  return (
    <div className={cn("grid gap-2.5", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-display text-[17px] leading-tight font-semibold tracking-[0.02em]">Every scoreline</h3>
        <button
          type="button"
          onClick={() => setShowTable((shown) => !shown)}
          className="touch-target rounded-md border border-bp-border bg-bp-surface-2 px-2 py-1 font-mono text-[11px] font-medium text-bp-text-muted"
        >
          {showTable ? "Hide table" : "Table"}
        </button>
      </div>

      <div
        role="img"
        aria-label={summary}
        onPointerMove={track}
        onPointerLeave={() => setHover(null)}
        className="relative grid max-w-[360px] grid-cols-[22px_repeat(6,minmax(0,1fr))] grid-rows-[repeat(6,minmax(0,1fr))_22px] gap-[3px]"
      >
        {[...GOAL_LEVELS].reverse().map((homeGoals) => (
          <HeatRow key={homeGoals} homeGoals={homeGoals} grid={grid} strongest={strongest} likeliest={likeliest} otherGrid={otherGrid} />
        ))}
        <span />
        {GOAL_LEVELS.map((awayGoals) => (
          <span key={awayGoals} className="grid place-items-center font-mono text-[11px] text-bp-text-muted">
            {awayGoals}
          </span>
        ))}
        {hover && (
          <div
            role="presentation"
            className="pointer-events-none absolute z-10 rounded-lg border border-bp-border bg-bp-surface-2 px-2.5 py-1.5 font-mono text-xs whitespace-nowrap shadow-[0_8px_24px_rgb(0_0_0/0.5)]"
            style={{ left: Math.min(hover.left, 200), top: Math.max(0, hover.top - 52) }}
          >
            <b className="font-medium text-bp-text">
              {home} {hover.home}–{hover.away} {away}
            </b>
            <br />
            <span className="text-bp-text-muted">{label}</span> <b className="font-medium text-bp-text">{percent(grid[hover.home][hover.away])}</b>
            {other && otherGrid && (
              <>
                <br />
                <span className="text-bp-text-muted">{other.label}</span> {percent(otherGrid[hover.home][hover.away])}
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex max-w-[360px] flex-wrap justify-between gap-1.5 font-mono text-[11px] text-bp-text-muted">
        <span>
          Rows: {home} goals · columns: {away} goals
        </span>
        <span className="inline-flex items-center gap-1.5">
          less
          <i aria-hidden="true" className="h-1.5 w-[70px] rounded-[3px] bg-[linear-gradient(90deg,#1B1B1F,#F4F4F5)]" />
          more likely
        </span>
      </div>

      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr>
                <th className="border-b border-bp-border p-1 text-right font-medium text-bp-text-muted">
                  {home} \ {away}
                </th>
                {GOAL_LEVELS.map((awayGoals) => (
                  <th key={awayGoals} scope="col" className="border-b border-bp-border p-1 text-right font-medium text-bp-text-muted">
                    {awayGoals}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {GOAL_LEVELS.map((homeGoals) => (
                <tr key={homeGoals}>
                  <th scope="row" className="border-b border-bp-border p-1 text-right font-medium text-bp-text-muted">
                    {homeGoals}
                  </th>
                  {GOAL_LEVELS.map((awayGoals) => (
                    <td key={awayGoals} className="border-b border-bp-border p-1 text-right">
                      {percent(grid[homeGoals][awayGoals])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function HeatRow({
  homeGoals,
  grid,
  strongest,
  likeliest,
  otherGrid,
}: {
  homeGoals: number;
  grid: number[][];
  strongest: number;
  likeliest: Markets["top_scores"][number];
  otherGrid: number[][] | null;
}) {
  return (
    <>
      <span className="grid place-items-center font-mono text-[11px] text-bp-text-muted">{homeGoals}</span>
      {GOAL_LEVELS.map((awayGoals) => {
        const probability = grid[homeGoals][awayGoals];
        const intensity = Math.sqrt(probability / strongest);
        const isTop = homeGoals === likeliest.home && awayGoals === likeliest.away;
        return (
          <span
            key={awayGoals}
            data-cell=""
            data-home={homeGoals}
            data-away={awayGoals}
            data-score={`${homeGoals}-${awayGoals}`}
            data-probability={probability}
            data-compare={otherGrid ? (otherGrid[homeGoals][awayGoals] * 100).toFixed(1) : undefined}
            data-top={isTop ? "" : undefined}
            className={cn(
              "relative grid aspect-square cursor-default place-items-center rounded font-mono text-[11px] font-medium transition-[background-color,color] duration-[400ms] motion-reduce:transition-none",
              homeGoals === awayGoals && "before:absolute before:-inset-px before:rounded-[5px] before:border before:border-dashed before:border-bp-text/25 before:content-['']",
              isTop && "shadow-[0_0_0_2px_var(--bp-bg),0_0_0_3px_var(--bp-text)]",
            )}
            style={{ background: heatShade(intensity), color: intensity >= 0.5 ? "#0A0A0B" : "#F4F4F5" }}
          >
            {probability >= LABEL_THRESHOLD ? (probability * 100).toFixed(probability < 0.01 ? 1 : 0) : ""}
          </span>
        );
      })}
    </>
  );
}
