import { describe, expect, it } from "vitest";

import { springEasing } from "./spring";

function samples(css: string): number[] {
  return css.slice("linear(".length, -1).split(",").map(Number);
}

describe("springEasing", () => {
  it("samples a damped spring into a CSS linear() function", () => {
    const { css } = springEasing(0.25, 0.42);
    expect(css).toMatch(/^linear\(.+\)$/);
    const points = samples(css);
    expect(points).toHaveLength(49);
    expect(points[0]).toBe(0);
    expect(points.at(-1)).toBe(1);
  });

  it("lasts one and a half spring periods so the settle is not cut off", () => {
    expect(springEasing(0.25, 0.42).ms).toBe(630);
  });

  it("overshoots 1 when there is bounce", () => {
    expect(Math.max(...samples(springEasing(0.25, 0.42).css))).toBeGreaterThan(1);
  });

  it("never overshoots without bounce", () => {
    expect(Math.max(...samples(springEasing(0, 0.42).css))).toBeLessThanOrEqual(1);
  });
});
