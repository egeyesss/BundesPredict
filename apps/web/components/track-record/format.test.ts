import { describe, expect, it } from "vitest";

import { axisTicks, formatDay, formatDayRange, isShortRecord, rpsDomain, scoredMatchdays, score, type MatchdayRow, type Period } from "./format";

function row(matchday: number, rps: number | null, nResolved = 9): MatchdayRow {
  return {
    season: "2627",
    matchday,
    n_fixtures: 9,
    n_resolved: nResolved,
    rps,
    log_loss: rps,
    hit_rate: 0.5,
    bookmaker_rps: rps === null ? null : rps - 0.01,
    base_rate_rps: rps === null ? null : 0.23,
    fixtures: [],
  };
}

describe("score", () => {
  it("prints four decimals so 0.2045 and 0.1967 line up", () => {
    expect(score(0.2)).toBe("0.2000");
    expect(score(0.19674)).toBe("0.1967");
  });
});

describe("formatDay", () => {
  it("reads the calendar date in UTC so server and browser agree", () => {
    expect(formatDay("2026-10-22")).toBe("22 Oct 2026");
  });

  it("collapses a one-day range", () => {
    expect(formatDayRange("2026-10-10T13:30:00Z", "2026-10-10T16:30:00Z")).toBe("10 Oct");
    expect(formatDayRange("2026-10-09T18:30:00Z", "2026-10-11T15:30:00Z")).toBe("9 Oct to 11 Oct");
  });
});

describe("axisTicks", () => {
  it("steps without float drift", () => {
    expect(axisTicks(0.12, 0.28, 0.04)).toEqual([0.12, 0.16, 0.2, 0.24, 0.28]);
  });
});

describe("scoredMatchdays", () => {
  it("drops matchdays without a scored match and sorts oldest first", () => {
    const rows = [row(7, 0.2), row(6, null, 0), row(5, 0.19)];

    expect(scoredMatchdays(rows).map((r) => r.matchday)).toEqual([5, 7]);
  });
});

describe("rpsDomain", () => {
  it("snaps to 0.04 steps around the data", () => {
    expect(rpsDomain([row(1, 0.2), row(2, 0.27)])).toEqual({ low: 0.16, high: 0.32 });
  });

  it("falls back to a sensible range with no data", () => {
    expect(rpsDomain([])).toEqual({ low: 0.12, high: 0.32 });
  });
});

describe("isShortRecord", () => {
  const period = (n: number | null): Period => ({
    kind: "live",
    label: "Live",
    since: null,
    model: n === null ? null : { n_fixtures: n, rps: 0.2, log_loss: 1, hit_rate: 0.5 },
    bookmaker: null,
    base_rate: null,
    calibration_error: null,
    forecasters: [],
  });

  it("flags fewer than 50 scored matches", () => {
    expect(isShortRecord(period(7))).toBe(true);
    expect(isShortRecord(period(50))).toBe(false);
    expect(isShortRecord(period(null))).toBe(false);
  });
});
