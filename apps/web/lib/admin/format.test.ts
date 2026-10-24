import { describe, expect, it } from "vitest";

import { axisScale, costStatus, fitLabel, formatAgo, formatMoney, formatPercent, labelEvery } from "./format";

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

describe("fitLabel", () => {
  // 6.8px is the average width of a 12px Inter character the chart budgets for.
  const CHAR_PX = 6.8;

  it("keeps a label that fits", () => {
    expect(fitLabel("lea.b@example.org", 180, CHAR_PX)).toBe("lea.b@example.org");
  });

  it("cuts a label to the space it has, ending in an ellipsis", () => {
    const label = fitLabel("jonas.w@example.com", 100, CHAR_PX);

    expect(label.endsWith("…")).toBe(true);
    expect(label.length * CHAR_PX).toBeLessThanOrEqual(100);
    expect("jonas.w@example.com".startsWith(label.slice(0, -1))).toBe(true);
  });

  it("never returns less than one character and the ellipsis", () => {
    expect(fitLabel("someone@example.com", 4, CHAR_PX)).toBe("s…");
  });
});
