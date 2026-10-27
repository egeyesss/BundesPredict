import { describe, expect, it } from "vitest";

import { overlapsSheet, placeBubble, sheetDockFor, type Box } from "./placement";

const viewport = { width: 1440, height: 900 };
const bubble = { width: 360, height: 300 };
const box = (left: number, top: number, width: number, height: number): Box => ({ left, top, width, height, right: left + width, bottom: top + height });
const place = (target: Box, preferred: "top" | "bottom" | "left" | "right", over: Partial<Parameters<typeof placeBubble>[0]> = {}) =>
  placeBubble({ target, bubble, viewport, preferred, headerHeight: 76, ...over });

describe("placeBubble", () => {
  it("puts the bubble on the preferred side when it fits", () => {
    const placement = place(box(500, 400, 300, 100), "bottom");
    expect(placement.side).toBe("bottom");
    expect(placement.y).toBe(400 + 100 + 16);
    expect(placement.x).toBe(500 + 150 - 180);
  });

  it("flips to the opposite side when the preferred one runs off the screen", () => {
    expect(place(box(500, 700, 300, 150), "bottom").side).toBe("top");
    expect(place(box(1300, 400, 120, 80), "right").side).toBe("left");
  });

  it("does not tuck the bubble under the header when flipping upward", () => {
    const placement = place(box(500, 300, 300, 100), "top");
    expect(placement.side).toBe("bottom");
  });

  it("clamps the bubble inside the viewport and aims the arrow at the target", () => {
    const placement = place(box(0, 400, 120, 80), "bottom");
    expect(placement.x).toBe(12);
    expect(placement.arrow).toBeGreaterThanOrEqual(18);
    const far = place(box(1380, 400, 60, 80), "bottom");
    expect(far.x + bubble.width).toBeLessThanOrEqual(viewport.width - 12);
  });

  it("falls back to below the target when nothing fits", () => {
    const tall = place(box(100, 100, 1200, 750), "right");
    expect(["bottom", "top", "left", "right"]).toContain(tall.side);
    expect(tall.y).toBeGreaterThanOrEqual(12);
  });

  it("docks as a sheet under 640px", () => {
    const phone = placeBubble({ target: box(16, 200, 343, 120), bubble: { width: 351, height: 320 }, viewport: { width: 375, height: 812 }, preferred: "right", headerHeight: 76 });
    expect(phone.side).toBe("sheet");
    expect(phone.x).toBe(12);
  });
});

describe("sheet docking", () => {
  it("docks at the bottom unless the target sits in the lower half", () => {
    expect(sheetDockFor(box(16, 200, 343, 100), 812)).toBe("bottom");
    expect(sheetDockFor(box(16, 700, 343, 90), 812)).toBe("top");
  });

  it("reports when the target is under the sheet", () => {
    expect(overlapsSheet(box(16, 600, 343, 100), "bottom", 320, 812, 76)).toBe(true);
    expect(overlapsSheet(box(16, 150, 343, 100), "bottom", 320, 812, 76)).toBe(false);
    expect(overlapsSheet(box(16, 100, 343, 100), "top", 320, 812, 76)).toBe(true);
    expect(overlapsSheet(box(16, 650, 343, 100), "top", 320, 812, 76)).toBe(false);
  });
});
