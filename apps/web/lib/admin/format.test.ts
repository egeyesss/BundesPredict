import { describe, expect, it } from "vitest";

import { axisScale, costStatus, formatAgo, formatMoney, formatPercent, labelEvery } from "./format";

describe("formatMoney", () => {
  it("shows cents as dollars with two decimals", () => {
    expect(formatMoney(3000)).toBe("$30.00");
    expect(formatMoney(14.2)).toBe("$0.14");
    expect(formatMoney(0)).toBe("$0.00");
  });
});

describe("formatPercent", () => {
  it("keeps one decimal and drops it for zero", () => {
    expect(formatPercent(0.0833)).toBe("8.3%");
    expect(formatPercent(0)).toBe("0%");
  });
});

describe("formatAgo", () => {
  const now = Date.parse("2026-10-22T12:00:00Z");
  it("steps from minutes to hours to days", () => {
    expect(formatAgo("2026-10-22T11:58:00Z", now)).toBe("2 min ago");
    expect(formatAgo("2026-10-22T09:00:00Z", now)).toBe("3 h ago");
    expect(formatAgo("2026-10-19T12:00:00Z", now)).toBe("3 d ago");
    expect(formatAgo("2026-10-22T12:00:30Z", now)).toBe("just now");
  });
});

describe("costStatus", () => {
  it("is healthy under 30% of revenue, watch under 50%, high above", () => {
    expect(costStatus(0.19)).toBe("healthy");
    expect(costStatus(0.3)).toBe("watch");
    expect(costStatus(0.51)).toBe("high");
    expect(costStatus(null)).toBeNull();
  });
});

describe("axisScale", () => {
  it("rounds the top up to a multiple so four gridlines land on whole numbers", () => {
    expect(axisScale(97, 40)).toEqual({ top: 120, ticks: [0, 30, 60, 90, 120] });
    expect(axisScale(0, 40)).toEqual({ top: 40, ticks: [0, 10, 20, 30, 40] });
  });
});

describe("labelEvery", () => {
  it("labels every bar for a week and thins out longer ranges", () => {
    expect([7, 30, 90].map(labelEvery)).toEqual([1, 7, 14]);
  });
});
