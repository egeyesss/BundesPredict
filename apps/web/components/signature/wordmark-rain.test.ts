import { describe, expect, it } from "vitest";

import {
  RainField,
  WORDMARK_SETTINGS,
  baseLayerAlpha,
  glyphSizeFor,
  rampActivity,
  stepIntervalMs,
  trailColor,
} from "./wordmark-rain";
import { DEFAULT_PALETTE } from "./palette";

/** Cycles through fixed values so the field is reproducible. */
const sequence = (...values: number[]) => {
  let index = 0;
  return () => values[index++ % values.length];
};

describe("locked settings", () => {
  it("matches the tuned values", () => {
    expect(WORDMARK_SETTINGS).toMatchObject({
      glyphScale: 0.15,
      minGlyphPx: 6,
      baseLayerAlpha: 0.35,
      stepsPerSecond: 18,
      density: 0.6,
      trailLength: 8,
      activeBoost: 2,
      activeRampMs: 400,
    });
  });

  it("uses half-width katakana plus digits", () => {
    expect(WORDMARK_SETTINGS.glyphs).toHaveLength(45 + 10);
    expect(WORDMARK_SETTINGS.glyphs.startsWith("ｱｲｳｴｵ")).toBe(true);
    expect(WORDMARK_SETTINGS.glyphs.endsWith("0123456789")).toBe(true);
  });
});

describe("glyphSizeFor", () => {
  it("is 15% of the font size", () => {
    expect(glyphSizeFor(140)).toBeCloseTo(21);
  });

  it("never goes below 6px", () => {
    expect(glyphSizeFor(20)).toBe(6);
    expect(glyphSizeFor(40)).toBe(6);
  });
});

describe("baseLayerAlpha", () => {
  it("is 35% at hero sizes and 60% below 40px", () => {
    expect(baseLayerAlpha(140)).toBe(0.35);
    expect(baseLayerAlpha(40)).toBe(0.35);
    expect(baseLayerAlpha(39.9)).toBe(0.6);
    expect(baseLayerAlpha(20)).toBe(0.6);
  });
});

describe("stepIntervalMs", () => {
  it("is 18 steps per second at rest and doubles while active", () => {
    expect(stepIntervalMs(0)).toBeCloseTo(1000 / 18);
    expect(stepIntervalMs(1)).toBeCloseTo(1000 / 36);
  });
});

describe("rampActivity", () => {
  it("moves toward the target at 1/400 per ms", () => {
    expect(rampActivity(0, 1, 100)).toBeCloseTo(0.25);
    expect(rampActivity(1, 0, 200)).toBeCloseTo(0.5);
  });

  it("does not overshoot", () => {
    expect(rampActivity(0.9, 1, 1000)).toBe(1);
    expect(rampActivity(0.1, 0, 1000)).toBe(0);
  });

  it("stays put at the target", () => {
    expect(rampActivity(1, 1, 50)).toBe(1);
  });
});

describe("trailColor", () => {
  it("runs from the red token to the dim red", () => {
    expect(trailColor(DEFAULT_PALETTE, 0).slice(0, 3)).toEqual(DEFAULT_PALETTE.red);
    expect(trailColor(DEFAULT_PALETTE, 1).slice(0, 3)).toEqual(DEFAULT_PALETTE.redDim);
  });

  it("fades the alpha along the trail but keeps a floor of 10%", () => {
    expect(trailColor(DEFAULT_PALETTE, 0)[3]).toBeCloseTo(1);
    expect(trailColor(DEFAULT_PALETTE, 1)[3]).toBeCloseTo(0.1);
    expect(trailColor(DEFAULT_PALETTE, 0.5)[3]).toBeLessThan(trailColor(DEFAULT_PALETTE, 0.25)[3]);
  });
});

describe("RainField", () => {
  it("lays out one column per 0.9 glyph widths", () => {
    const field = new RainField(100, 40, 10, Math.random);
    expect(field.columns).toHaveLength(Math.ceil(100 / 9));
    expect(field.rows).toBe(4);
    expect(field.columnWidth).toBeCloseTo(100 / field.columns.length);
  });

  it("activates columns by density", () => {
    const all = new RainField(100, 40, 10, () => 0, 1);
    expect(all.columns.every((column) => column.active)).toBe(true);
    const none = new RainField(100, 40, 10, () => 0.99, 0);
    expect(none.columns.some((column) => column.active)).toBe(false);
  });

  it("moves each head by its speed, with the boost capped at 1.6", () => {
    const field = new RainField(20, 40, 10, sequence(0.5), 1);
    const before = field.columns.map((column) => column.head);
    field.step(1, 0);
    field.step(5, 0);
    field.columns.forEach((column, index) => {
      expect(column.head).toBeCloseTo(before[index] + column.speed * 1 + column.speed * 1.6);
    });
  });

  it("restarts a column once its trail has left the bottom", () => {
    const field = new RainField(20, 40, 10, () => 0.5, 1);
    field.columns[0].head = field.rows + WORDMARK_SETTINGS.trailLength + 1;
    const replaced = field.columns[0];
    field.step(1, 0);
    expect(field.columns[0]).not.toBe(replaced);
    expect(field.columns[0].head).toBeLessThanOrEqual(0);
  });

  it("raises the share of active columns as activity rises", () => {
    const field = new RainField(100, 40, 10, Math.random);
    expect(field.density(0)).toBeCloseTo(0.6);
    expect(field.density(1)).toBeCloseTo(0.6 + 0.4 * 0.6);
  });

  it("only draws glyphs from the configured set", () => {
    const field = new RainField(100, 40, 10, Math.random);
    for (const column of field.columns) {
      for (const glyph of column.glyphs) expect(WORDMARK_SETTINGS.glyphs).toContain(glyph);
    }
  });
});
