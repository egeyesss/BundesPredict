import { readFileSync } from "node:fs";
import path from "node:path";

const playwrightPackage = path.resolve(
  import.meta.dirname,
  "../../node_modules/@playwright/test/package.json",
);

export function playwrightImage() {
  const { version } = JSON.parse(readFileSync(playwrightPackage, "utf8"));
  return `mcr.microsoft.com/playwright:v${version}-noble`;
}
