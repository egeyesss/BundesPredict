// Rebuilds public/crests/manifest.json and the 48px and 96px PNGs (Gmail drops
// SVG, so the matchday email links the PNGs) from scripts/crests.json and the
// SVGs in public/crests. Run with `npm run crests:build` after adding a club.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import sharp from "sharp";

const webRoot = path.resolve(import.meta.dirname, "..");
const crestDir = path.join(webRoot, "public/crests");
const pngDir = path.join(crestDir, "png");
const PNG_SIZES = [48, 96];

const clubs = JSON.parse(await readFile(path.join(import.meta.dirname, "crests.json"), "utf8"));
const manifest = {};

await mkdir(pngDir, { recursive: true });

for (const [code, club] of Object.entries(clubs)) {
  const file = `${code}.svg`;
  const svg = await readFile(path.join(crestDir, file), "utf8");
  if (!/<svg[^>]*viewBox=/.test(svg)) {
    throw new Error(`${file} has no viewBox, so it cannot scale to the crest sizes`);
  }

  manifest[code] = {
    name: club.name,
    file,
    primary: club.primary,
    secondary: club.secondary,
    dark: club.dark,
    source: club.source,
  };

  for (const size of PNG_SIZES) {
    await sharp(Buffer.from(svg), { density: 384 })
      .resize(size, size, { fit: "inside", background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png({ compressionLevel: 9 })
      .toFile(path.join(pngDir, `${code}-${size}.png`));
  }
}

await writeFile(path.join(crestDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Wrote manifest and ${Object.keys(manifest).length * PNG_SIZES.length} PNGs`);
