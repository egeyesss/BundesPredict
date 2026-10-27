import { describe, expect, it } from "vitest";

import { meFor } from "@/lib/api/mocks/data";

import { quotaSummary } from "@/components/brand/nav";
import type { Me } from "@/lib/api/types";

import { chatsLeft, formatDay, formatTimeOfDay, navUserFromMe, planState, quotaPlan } from "./plan";

const proMe = meFor("pro");
// A demo visitor who finished the Stripe test checkout: Pro on paper, still on the 10-chat demo cap.
const demoProMe: Me = { ...meFor("demo"), plan: "pro", subscription: proMe.subscription };

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
      isDemo: false,
    });
  });

  it("keeps the demo allowance in the island after a test checkout", () => {
    expect(quotaSummary(navUserFromMe(demoProMe))).toBe("8 of 10 demo chats left");
    expect(quotaSummary(navUserFromMe(proMe))).toBe("Pro · fair use");
  });
});

describe("quotaPlan", () => {
  it("counts a demo user against the demo allowance even when their plan is Pro", () => {
    expect(quotaPlan(demoProMe)).toBe("demo");
    expect(quotaPlan(meFor("demo"))).toBe("demo");
    expect(quotaPlan(proMe)).toBe("pro");
    expect(quotaPlan(meFor("free"))).toBe("free");
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
