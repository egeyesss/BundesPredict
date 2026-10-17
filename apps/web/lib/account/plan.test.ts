import { describe, expect, it } from "vitest";

import { meFor } from "@/lib/api/mocks/data";

import { chatsLeft, formatDay, formatTimeOfDay, navUserFromMe, planState } from "./plan";

const proMe = meFor("pro");

describe("planState", () => {
  it("tells apart every state the account page renders", () => {
    expect(planState(meFor("free"))).toBe("free");
    expect(planState({ ...meFor("free"), usage: { ...meFor("free").usage, used: 3 } })).toBe("free_exhausted");
    expect(planState(proMe)).toBe("pro");
    expect(planState({ ...proMe, subscription: { ...proMe.subscription!, cancel_at_period_end: true } })).toBe("cancelling");
    expect(planState({ ...proMe, subscription: { ...proMe.subscription!, status: "past_due" } })).toBe("past_due");
    expect(planState(meFor("demo"))).toBe("demo");
  });

  it("treats a Pro plan without a subscription row as plain Pro", () => {
    expect(planState({ ...proMe, subscription: null })).toBe("pro");
  });
});

describe("chatsLeft", () => {
  it("never goes negative", () => {
    expect(chatsLeft({ used: 5, limit: 3, resets_at: "" })).toBe(0);
    expect(chatsLeft({ used: 1, limit: 3, resets_at: "" })).toBe(2);
  });
});

describe("navUserFromMe", () => {
  it("maps the fields the island needs", () => {
    expect(navUserFromMe(meFor("free"))).toEqual({
      name: "Sam Rivera",
      email: "sam.rivera@example.com",
      plan: "free",
      chatsUsed: 1,
      chatsLimit: 3,
    });
  });
});

describe("date formatting", () => {
  it("formats a day in the given zone, not the machine's", () => {
    expect(formatDay("2026-11-02T03:00:00Z", "America/Toronto")).toBe("Nov 1");
    expect(formatDay("2026-11-02T03:00:00Z", "Europe/Berlin")).toBe("Nov 2");
  });

  it("formats the daily reset as a local time of day", () => {
    expect(formatTimeOfDay("2026-10-16T00:00:00Z", "America/Toronto")).toBe("8:00 PM");
  });
});
