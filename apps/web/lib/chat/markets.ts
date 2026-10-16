import type { Markets } from "@/lib/api/types";

/** The heatmap shows 0 to 5 goals a side; the API grid goes to 10 and the tail is negligible. */
export const HEATMAP_SIZE = 6;

/** Rows are home goals, columns are away goals, as in the API's `score_grid`. */
export function scoreGrid(markets: Markets): number[][] {
  return markets.score_grid.slice(0, HEATMAP_SIZE).map((row) => row.slice(0, HEATMAP_SIZE));
}

/** A clean sheet for the home side is every score where the away side stays on zero. */
export function cleanSheets(markets: Markets): { home: number; away: number } {
  const grid = markets.score_grid;
  return {
    home: grid.reduce((sum, row) => sum + (row[0] ?? 0), 0),
    away: (grid[0] ?? []).reduce((sum, probability) => sum + probability, 0),
  };
}

export type MarketRow = { name: string; sub?: string; now: number; before: number };

export function marketRows(now: Markets, before: Markets, home: string, away: string): MarketRow[] {
  const nowSheets = cleanSheets(now);
  const beforeSheets = cleanSheets(before);
  return [
    { name: "Over 2.5 goals", now: now.p_over_2_5, before: before.p_over_2_5 },
    { name: "Under 2.5 goals", now: now.p_under_2_5, before: before.p_under_2_5 },
    { name: "Both teams score", now: now.p_btts, before: before.p_btts },
    { name: `${home} clean sheet`, sub: `${away} don't score`, now: nowSheets.home, before: beforeSheets.home },
    { name: `${away} clean sheet`, sub: `${home} don't score`, now: nowSheets.away, before: beforeSheets.away },
  ];
}

/** Neutral arrows: green and red only ever mean win and lose. */
export function formatMarketChange(now: number, before: number): string {
  const points = (now - before) * 100;
  if (Math.abs(points) < 0.5) return "no change";
  return `${points > 0 ? "▲ +" : "▼ −"}${Math.abs(points).toFixed(1)}`;
}

/** A sequential ramp from the card surface to near white, so it never borrows the win and lose colours. */
export function heatShade(intensity: number): string {
  return `color-mix(in oklab, #F4F4F5 ${Math.round(intensity * 100)}%, #1B1B1F)`;
}
