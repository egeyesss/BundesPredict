import { describe, expect, it } from "vitest";

import { trackRecord } from "@/lib/api/mocks/data";
import type { TrackRecord } from "@/lib/api/types";

import { BACKTEST_SUMMARY, liveRecordView } from "./track-record-teaser";

describe("BACKTEST_SUMMARY", () => {
  it("carries the numbers from the backtest report", () => {
    expect(BACKTEST_SUMMARY).toMatchObject({ matches: 1827, modelRps: 0.2045, marketRps: 0.1967 });
  });
});

describe("liveRecordView", () => {
  it("shows the live numbers when matches have been scored", () => {
    const view = liveRecordView(trackRecord);
    expect(view).toEqual({ kind: "scored", matches: 63, modelRps: 0.2086, bookmakerRps: 0.2012, label: "Live since 2026-08-28" });
  });

  it("says backtest only when nothing has been scored yet", () => {
    const empty: TrackRecord = { ...trackRecord, live: { ...trackRecord.live, model: null, bookmaker: null } };
    expect(liveRecordView(empty)).toEqual({ kind: "empty" });
  });

  it("treats a zero-fixture live period as empty", () => {
    const zero: TrackRecord = {
      ...trackRecord,
      live: { ...trackRecord.live, model: { n_fixtures: 0, rps: 0, log_loss: 0, hit_rate: 0 } },
    };
    expect(liveRecordView(zero)).toEqual({ kind: "empty" });
  });

  it("still shows the model when the bookmaker comparison is missing", () => {
    const noMarket: TrackRecord = { ...trackRecord, live: { ...trackRecord.live, bookmaker: null } };
    expect(liveRecordView(noMarket)).toMatchObject({ kind: "scored", bookmakerRps: null });
  });
});
