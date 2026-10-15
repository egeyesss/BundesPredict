import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import sharp from "sharp";
import { describe, expect, it } from "vitest";

import { clubColors, crestManifest, crestUrl, DEFAULT_CHIP_COLORS } from "./brand";

const crestDir = path.resolve(import.meta.dirname, "../public/crests");
const codes = Object.keys(crestManifest);

describe("crest manifest", () => {
  it("covers the 18 clubs of the 2026/27 season", () => {
    expect(codes).toHaveLength(18);
  });

  it("flags only the mostly-black crests as dark", () => {
    const dark = codes.filter((code) => crestManifest[code].dark).sort();
    expect(dark).toEqual(["BMG", "SCF", "SVE"]);
  });

  it.each(codes)("%s has a self-hosted SVG with a viewBox", (code) => {
    const svg = readFileSync(path.join(crestDir, crestManifest[code].file), "utf8");
    expect(svg).toMatch(/<svg[^>]*viewBox=/);
  });

  it.each(codes)("%s records a name, a source URL and two hex colours", (code) => {
    const entry = crestManifest[code];
    expect(entry.name.length).toBeGreaterThan(2);
    expect(entry.source).toMatch(/^https:\/\/upload\.wikimedia\.org\//);
    expect(entry.primary).toMatch(/^#[0-9A-F]{6}$/);
    expect(entry.secondary).toMatch(/^#[0-9A-F]{6}$/);
  });

  it.each(codes.flatMap((code) => [[code, 48], [code, 96]] as const))(
    "%s has a %ipx PNG for the email",
    async (code, size) => {
      const file = path.join(crestDir, "png", `${code}-${size}.png`);
      expect(existsSync(file)).toBe(true);
      const { width, height, format } = await sharp(file).metadata();
      expect(format).toBe("png");
      expect(Math.max(width ?? 0, height ?? 0)).toBe(size);
    },
  );
});

describe("crestUrl", () => {
  it("builds the public path for a known club", () => {
    expect(crestUrl("FCB")).toBe("/crests/FCB.svg");
  });

  it("returns null for a club without an asset", () => {
    expect(crestUrl("NEW")).toBeNull();
  });
});

describe("clubColors", () => {
  it("returns the manifest colours for a known club", () => {
    expect(clubColors("BVB")).toEqual({ primary: "#FDE100", secondary: "#000000" });
  });

  it("falls back to a neutral pair for an unknown club", () => {
    expect(clubColors("NEW")).toEqual(DEFAULT_CHIP_COLORS);
  });
});
