import { describe, expect, it } from "vitest";

import { STEPS, SCREEN_LABEL, stepsOnPath } from "./steps";

describe("tour steps", () => {
  it("has the fifteen stops, split four, six, two and three across the screens", () => {
    expect(STEPS).toHaveLength(15);
    const count = (screen: string) => STEPS.filter((step) => step.screen === screen).length;
    expect([count("matchday"), count("chat"), count("record"), count("admin")]).toEqual([4, 6, 2, 3]);
  });

  it("keeps each screen's stops together and in page order", () => {
    expect(STEPS.map((step) => step.screen)).toEqual([
      ...Array(4).fill("matchday"),
      ...Array(6).fill("chat"),
      ...Array(2).fill("record"),
      ...Array(3).fill("admin"),
    ]);
  });

  it("gives every stop unique ids, anchors, copy and a screen label", () => {
    expect(new Set(STEPS.map((step) => step.id)).size).toBe(STEPS.length);
    for (const step of STEPS) {
      expect(step.anchors.length).toBeGreaterThan(0);
      expect(step.title && step.what && step.how).toBeTruthy();
      expect(SCREEN_LABEL[step.screen]).toBeTruthy();
    }
  });

  it("finds the stops for a pathname", () => {
    expect(stepsOnPath("/matchday").map((step) => step.id)).toEqual(["fixture", "odds", "xg", "ask"]);
    expect(stepsOnPath("/chat").length).toBe(6);
    expect(stepsOnPath("/chat/abc").length).toBe(6);
    expect(stepsOnPath("/account")).toEqual([]);
  });

  it("states only claims that match the code", () => {
    const copy = STEPS.map((step) => `${step.what} ${step.how}`).join(" ");
    expect(copy).toContain("05:00 UTC");
    expect(copy).not.toMatch(/Monday|03:00|unlimited/i);
    expect(copy).toContain("10");
    expect(copy).toContain("100");
    expect(copy).toContain("$4.55");
    expect(copy).not.toContain("—");
  });
});
