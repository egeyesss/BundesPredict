import { describe, expect, it } from "vitest";

import { PITCH, buildPitch, projectPitch, sweepGlow, sweepX } from "./pitch";

const camera = { width: 1000, height: 600, elapsedSeconds: 0, drifting: false };

describe("buildPitch", () => {
  const pitch = buildPitch();

  it("draws the markings as digit glyphs", () => {
    expect(pitch.lines.length).toBeGreaterThan(400);
    expect(pitch.lines.every((point) => /^\d$/.test(point.glyph))).toBe(true);
  });

  it("marks the centre spot and both penalty spots", () => {
    const spots = pitch.lines.filter((point) => point.spot);
    expect(spots).toHaveLength(3);
    expect(spots).toContainEqual(expect.objectContaining({ x: 0, z: 0 }));
    expect(spots.map((spot) => spot.x).sort((a, b) => a - b)).toEqual([-41.5, 0, 41.5]);
  });

  it("keeps every point on the 105 by 68 metre pitch", () => {
    for (const point of [...pitch.lines, ...pitch.field]) {
      expect(Math.abs(point.x)).toBeLessThanOrEqual(PITCH.halfLength + 1e-6);
      expect(Math.abs(point.z)).toBeLessThanOrEqual(PITCH.halfWidth + 1e-6);
    }
  });

  it("is deterministic so the server and client frames agree", () => {
    expect(buildPitch()).toEqual(pitch);
  });
});

describe("projectPitch", () => {
  it("puts the pitch centre at the camera centre with no scaling", () => {
    const projected = projectPitch({ x: 0, z: 0 }, camera);
    expect(projected.x).toBeCloseTo(500);
    expect(projected.y).toBeCloseTo(360);
    expect(projected.scale).toBeCloseTo(1);
  });

  it("draws the near touchline larger than the far one", () => {
    const near = projectPitch({ x: 0, z: -PITCH.halfWidth }, camera);
    const far = projectPitch({ x: 0, z: PITCH.halfWidth }, camera);
    expect(near.scale).toBeGreaterThan(far.scale);
  });

  it("drifts only when asked to", () => {
    const point = { x: 50, z: 0 };
    const later = { ...camera, elapsedSeconds: 26 };
    expect(projectPitch(point, { ...later, drifting: true }).x).not.toBeCloseTo(projectPitch(point, { ...camera, drifting: true }).x);
    expect(projectPitch(point, later).x).toBeCloseTo(projectPitch(point, camera).x);
  });
});

describe("sweep", () => {
  it("travels along the pitch and starts again from the far end", () => {
    expect(sweepX(1)).toBeGreaterThan(sweepX(0));
    expect(sweepX(0)).toBeLessThan(-PITCH.halfLength);
    expect(sweepX(1000)).toBeGreaterThanOrEqual(sweepX(0) - 1e-9);
  });

  it("lights up points under the sweep and no others", () => {
    expect(sweepGlow(10, 10)).toBeCloseTo(1);
    expect(sweepGlow(40, 10)).toBeLessThan(0.001);
    expect(sweepGlow(10, null)).toBe(0);
  });
});
