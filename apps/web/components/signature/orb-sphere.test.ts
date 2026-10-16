import { describe, expect, it } from "vitest";

import {
  ORB_SETTINGS,
  ORB_TARGETS,
  buildSphere,
  depthAlpha,
  easeToward,
  glyphPxFor,
  pointCountFor,
  spinRate,
  usesDots,
} from "./orb-sphere";

describe("locked settings", () => {
  it("matches the tuned values", () => {
    expect(ORB_SETTINGS).toMatchObject({
      glyphsAt280px: 380,
      glyphScale: 0.055,
      dotsBelowGlyphPx: 6,
      axisTiltRad: 0.35,
      idleSpinRadPerSec: 0.25,
      thinkingSpinMultiplier: 2,
      thinkingRipple: 0.15,
      toolPulseMs: 700,
      coreGlow: 0.6,
      depthFadeExponent: 1.5,
      stateRampMs: 400,
      doneHoldMs: 1200,
      errorJitterMs: 300,
    });
    expect(ORB_SETTINGS.sizes).toEqual({ chatHeader: 24, message: 56, stage: 280 });
    expect(ORB_SETTINGS.glyphs).toBe("0123456789");
  });
});

describe("pointCountFor", () => {
  it("is 380 at 280px and above", () => {
    expect(pointCountFor(280)).toBe(380);
    expect(pointCountFor(560)).toBe(380);
  });

  it("scales with the square root of the size below that", () => {
    expect(pointCountFor(56)).toBe(Math.round(380 * Math.sqrt(56 / 280)));
    expect(pointCountFor(24)).toBe(Math.round(380 * Math.sqrt(24 / 280)));
  });

  it("never drops below 48", () => {
    expect(pointCountFor(4)).toBe(48);
  });
});

describe("buildSphere", () => {
  const points = buildSphere(380);

  it("returns the requested number of points", () => {
    expect(points).toHaveLength(380);
  });

  it("puts every point on the unit sphere", () => {
    for (const { x, y, z } of points) expect(Math.hypot(x, y, z)).toBeCloseTo(1, 6);
  });

  it("covers the sphere from pole to pole", () => {
    const ys = points.map((point) => point.y);
    expect(Math.max(...ys)).toBeGreaterThan(0.99);
    expect(Math.min(...ys)).toBeLessThan(-0.99);
  });

  it("is spread evenly front to back", () => {
    const front = points.filter((point) => point.z > 0).length;
    expect(Math.abs(front - 190)).toBeLessThan(15);
  });
});

describe("glyph size", () => {
  it("is 5.5% of the orb", () => {
    expect(glyphPxFor(280)).toBeCloseTo(15.4);
  });

  it("switches to dots below 6px glyphs, which covers the 24px and 56px orbs", () => {
    expect(usesDots(24)).toBe(true);
    expect(usesDots(56)).toBe(true);
    expect(usesDots(280)).toBe(false);
    expect(usesDots(6 / 0.055)).toBe(false);
  });
});

describe("depthAlpha", () => {
  it("runs from 8% at the back to fully opaque at the front", () => {
    expect(depthAlpha(0)).toBeCloseTo(0.08);
    expect(depthAlpha(1)).toBeCloseTo(1);
  });

  it("falls off with the 1.5 exponent", () => {
    expect(depthAlpha(0.5)).toBeCloseTo(0.08 + 0.92 * 0.5 ** 1.5);
  });
});

describe("spinRate", () => {
  it("is 0.25 rad/s idle and doubles when fully engaged", () => {
    expect(spinRate(0)).toBeCloseTo(0.25);
    expect(spinRate(1)).toBeCloseTo(0.5);
  });
});

describe("easeToward", () => {
  it("moves a fraction dt/0.4 of the way each call", () => {
    expect(easeToward(0, 1, 0.1)).toBeCloseTo(0.25);
  });

  it("lands on the target after the ramp time and never overshoots", () => {
    expect(easeToward(0, 1, 0.4)).toBe(1);
    expect(easeToward(0, 1, 2)).toBe(1);
  });
});

describe("state targets", () => {
  it("covers every phase", () => {
    expect(Object.keys(ORB_TARGETS).sort()).toEqual(["done", "error", "idle", "thinking", "tool"]);
  });

  it("only the error phase desaturates", () => {
    expect(ORB_TARGETS.error.grey).toBe(1);
    for (const phase of ["idle", "thinking", "tool", "done"] as const) expect(ORB_TARGETS[phase].grey).toBe(0);
  });

  it("glows brightest while a tool runs and dimmest in error", () => {
    const glows = Object.values(ORB_TARGETS).map((target) => target.glow);
    expect(ORB_TARGETS.tool.glow).toBe(Math.max(...glows));
    expect(ORB_TARGETS.error.glow).toBe(Math.min(...glows));
  });
});
