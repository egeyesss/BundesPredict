import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(path.join(import.meta.dirname, "tokens.css"), "utf8");

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`token --${name} is not declared in tokens.css`);
  return match[1].trim();
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(foreground: string, background: string): number {
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort(
    (a, b) => b - a,
  );
  return (lighter + 0.05) / (darker + 0.05);
}

describe("design tokens", () => {
  const expected: Record<string, string> = {
    "bp-bg": "#0A0A0B",
    "bp-surface-1": "#131316",
    "bp-surface-2": "#1B1B1F",
    "bp-border": "#2A2A30",
    "bp-text": "#F4F4F5",
    "bp-text-muted": "#A1A1AA",
    "bp-red": "#D20515",
    "bp-red-text": "#FF4D5A",
    "bp-red-dim": "#5C0209",
    "bp-red-glow": "rgb(210 5 21 / 0.45)",
    "odds-win": "#22C55E",
    "odds-win-text": "#4ADE80",
    "odds-lose": "#D20515",
    "odds-draw": "#71717A",
    "odds-draw-lead": "#D4D4D8",
    "bp-up": "#22C55E",
    "bp-down": "#FF4D5A",
    "bp-radius": "10px",
    "bp-radius-chip": "6px",
  };

  it.each(Object.entries(expected))("--%s is %s", (name, value) => {
    expect(token(name)).toBe(value);
  });

  describe("contrast on the surfaces text sits on", () => {
    const surfaces = ["bp-bg", "bp-surface-1", "bp-surface-2"] as const;

    it.each(surfaces)("primary and muted text reach 4.5:1 on %s", (surface) => {
      expect(contrast(token("bp-text"), token(surface))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(token("bp-text-muted"), token(surface))).toBeGreaterThanOrEqual(4.5);
    });

    it("small red text reaches 6:1 on the page background", () => {
      expect(contrast(token("bp-red-text"), token("bp-bg"))).toBeGreaterThanOrEqual(6);
    });

    it("small red text reaches 4.5:1 on raised surfaces", () => {
      expect(contrast(token("bp-red-text"), token("bp-surface-2"))).toBeGreaterThanOrEqual(4.5);
    });

    it("win and draw-lead labels reach 4.5:1 on cards", () => {
      expect(contrast(token("odds-win-text"), token("bp-surface-1"))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(token("odds-draw-lead"), token("bp-surface-1"))).toBeGreaterThanOrEqual(4.5);
    });

    it("white text on a red fill reaches 4.5:1", () => {
      expect(contrast("#FFFFFF", token("bp-red"))).toBeGreaterThanOrEqual(4.5);
    });

    it("the red fill reads as a shape (3:1) on the page background", () => {
      expect(contrast(token("bp-red"), token("bp-bg"))).toBeGreaterThanOrEqual(3);
    });
  });
});
