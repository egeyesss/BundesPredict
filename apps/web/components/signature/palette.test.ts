import { describe, expect, it } from "vitest";

import { DEFAULT_PALETTE, parseColor, readPalette } from "./palette";

describe("parseColor", () => {
  it("reads six-digit hex", () => {
    expect(parseColor("#D20515")).toEqual([210, 5, 21]);
    expect(parseColor(" #ff4d5a ")).toEqual([255, 77, 90]);
  });

  it("reads three-digit hex", () => {
    expect(parseColor("#fff")).toEqual([255, 255, 255]);
  });

  it("reads rgb() with commas or spaces and ignores alpha", () => {
    expect(parseColor("rgb(210, 5, 21)")).toEqual([210, 5, 21]);
    expect(parseColor("rgb(210 5 21 / 0.45)")).toEqual([210, 5, 21]);
  });

  it("returns null for anything else", () => {
    expect(parseColor("")).toBeNull();
    expect(parseColor("red")).toBeNull();
  });
});

describe("readPalette", () => {
  it("falls back to the token values when the variables are not defined", () => {
    expect(readPalette(document.documentElement)).toEqual(DEFAULT_PALETTE);
  });

  it("reads the design tokens from the element's computed style", () => {
    const element = document.createElement("div");
    element.style.setProperty("--bp-red-text", "#010203");
    document.body.append(element);
    expect(readPalette(element).redText).toEqual([1, 2, 3]);
    expect(readPalette(element).red).toEqual(DEFAULT_PALETTE.red);
    element.remove();
  });
});
