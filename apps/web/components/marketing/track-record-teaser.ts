import type { TrackRecord } from "@/lib/api/types";

/** From the walk-forward backtest report: 1,827 matches predicted out of sample across five seasons. */
export const BACKTEST_SUMMARY = {
  matches: 1827,
  seasons: 5,
  modelRps: 0.2045,
  marketRps: 0.1967,
} as const;

export type LiveRecordView =
  | { kind: "scored"; matches: number; modelRps: number; bookmakerRps: number | null; label: string }
  | { kind: "empty" };

/** Reduces the endpoint's live period to what the teaser shows; no scored fixtures means "backtest only". */
export function liveRecordView(record: TrackRecord): LiveRecordView {
  const { model, bookmaker, label } = record.live;
  if (!model || model.n_fixtures === 0) return { kind: "empty" };
  return { kind: "scored", matches: model.n_fixtures, modelRps: model.rps, bookmakerRps: bookmaker?.rps ?? null, label };
}
