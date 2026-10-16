import { describe, expect, it } from "vitest";

import { chatsLeft, isExhausted, meterText, resetTimeText } from "./quota";

const usage = (used: number, limit: number) => ({ used, limit, resets_at: "2026-10-16T00:00:00Z" });

describe("meterText", () => {
  it("counts the free plan's chats left today", () => {
    expect(meterText("free", usage(1, 3))).toBe("2 of 3 free chats left today");
    expect(meterText("free", usage(3, 3))).toBe("0 of 3 free chats left today");
  });

  it("counts a demo's chats in total", () => {
    expect(meterText("demo", usage(2, 10))).toBe("8 of 10 demo chats left");
  });

  it("calls the pro plan fair use instead of showing the 100 cap", () => {
    expect(meterText("pro", usage(12, 100))).toBe("Pro · fair use");
  });
});

describe("chatsLeft and isExhausted", () => {
  it("never goes below zero", () => {
    expect(chatsLeft(usage(5, 3))).toBe(0);
    expect(isExhausted("free", usage(3, 3))).toBe(true);
    expect(isExhausted("free", usage(2, 3))).toBe(false);
  });

  it("does not lock a pro user out at the fair-use cap in the interface", () => {
    expect(isExhausted("pro", usage(100, 100))).toBe(false);
  });
});

describe("resetTimeText", () => {
  it("shows the reset in the viewer's own clock", () => {
    expect(resetTimeText("2026-10-16T00:00:00Z", { timeZone: "America/Toronto", locale: "en-US" })).toBe("8:00 PM");
  });
});
