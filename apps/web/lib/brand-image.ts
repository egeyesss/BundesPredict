import { readFile } from "node:fs/promises";
import { join } from "node:path";

/** Barlow Condensed Bold for the generated icons and share image; next/og cannot read next/font. */
export async function loadDisplayFont() {
  return readFile(join(process.cwd(), "assets/fonts/BarlowCondensed-Bold.ttf"));
}

export const DISPLAY_FONT = { name: "Barlow Condensed", style: "normal", weight: 700 } as const;
