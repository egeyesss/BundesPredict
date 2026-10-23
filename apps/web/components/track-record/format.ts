import type { TrackRecord } from "@/lib/api/types";

export type Period = TrackRecord["live"];
export type MatchdayRow = TrackRecord["matchdays"][number];
export type CalibrationBin = TrackRecord["calibration"][number];

/** Fewer scored matches than this and a single result still moves the averages visibly. */
export const SHORT_RECORD_MATCHES = 50;

export const score = (value: number) => value.toFixed(4);

export const percent = (share: number) => `${Math.round(share * 100)}%`;

const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const SHORT_DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export function formatDay(isoDate: string): string {
  return DAY.format(new Date(isoDate));
}

export function formatDayRange(firstIso: string, lastIso: string): string {
  const first = SHORT_DAY.format(new Date(firstIso));
  const last = SHORT_DAY.format(new Date(lastIso));
  return first === last ? first : `${first} to ${last}`;
}

/** Evenly spaced axis values from `start` to at most `end`, avoiding float drift in the labels. */
export function axisTicks(start: number, end: number, step: number): number[] {
  const count = Math.floor((end - start) / step + 1e-9);
  return Array.from({ length: count + 1 }, (_, index) => Number((start + index * step).toFixed(6)));
}

export type LiveSeriesKey = "rps" | "bookmaker_rps" | "base_rate_rps";

/** Matchdays with at least one scored match, oldest first, for the per-matchday chart. */
export function scoredMatchdays(matchdays: readonly MatchdayRow[]): MatchdayRow[] {
  return matchdays.filter((row) => row.n_resolved > 0).sort((a, b) => a.matchday - b.matchday);
}

/** The y-range for the RPS chart: the data plus a little air, snapped to 0.04 steps. */
export function rpsDomain(rows: readonly MatchdayRow[]): { low: number; high: number } {
  const values = rows.flatMap((row) => [row.rps, row.bookmaker_rps, row.base_rate_rps]).filter((v): v is number => v !== null);
  if (values.length === 0) return { low: 0.12, high: 0.32 };
  const low = Math.floor((Math.min(...values) - 0.01) / 0.04) * 0.04;
  const high = Math.ceil((Math.max(...values) + 0.01) / 0.04) * 0.04;
  return { low: Number(low.toFixed(2)), high: Number(high.toFixed(2)) };
}

export function isShortRecord(period: Period): boolean {
  return period.model !== null && period.model.n_fixtures < SHORT_RECORD_MATCHES;
}
