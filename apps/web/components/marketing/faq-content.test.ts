import { describe, expect, it } from "vitest";

import { FAQ_ENTRIES, nextFaqIndex } from "./faq-content";

describe("nextFaqIndex", () => {
  it("moves down and up, wrapping at the ends", () => {
    expect(nextFaqIndex("ArrowDown", 0, 5)).toBe(1);
    expect(nextFaqIndex("ArrowDown", 4, 5)).toBe(0);
    expect(nextFaqIndex("ArrowUp", 0, 5)).toBe(4);
    expect(nextFaqIndex("ArrowUp", 3, 5)).toBe(2);
  });

  it("jumps to the first and last question", () => {
    expect(nextFaqIndex("Home", 3, 5)).toBe(0);
    expect(nextFaqIndex("End", 1, 5)).toBe(4);
  });

  it("ignores every other key", () => {
    expect(nextFaqIndex("Tab", 2, 5)).toBeNull();
    expect(nextFaqIndex("Enter", 2, 5)).toBeNull();
  });
});

describe("FAQ_ENTRIES", () => {
  it("has unique ids and never uses betting language", () => {
    expect(new Set(FAQ_ENTRIES.map((entry) => entry.id)).size).toBe(FAQ_ENTRIES.length);
    const copy = FAQ_ENTRIES.flatMap((entry) => [entry.question, entry.answer]).join(" ").toLowerCase();
    expect(copy).not.toMatch(/\b(tips?|stake|bookie|beat the)\b/);
  });

  it("states the real backtest numbers", () => {
    const good = FAQ_ENTRIES.find((entry) => entry.id === "good");
    expect(good?.answer).toContain("1,827");
    expect(good?.answer).toContain("0.2045");
    expect(good?.answer).toContain("0.1967");
  });
});
