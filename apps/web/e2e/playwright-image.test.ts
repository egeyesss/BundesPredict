import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { playwrightImage } from "./support/playwright-image.mjs";

const webRoot = path.resolve(import.meta.dirname, "..");
const workflow = readFileSync(
  path.resolve(webRoot, "../../.github/workflows/ci.yml"),
  "utf8",
);

describe("playwright docker image", () => {
  it("is pinned to the installed @playwright/test version", () => {
    const { version } = JSON.parse(
      readFileSync(
        path.join(webRoot, "node_modules/@playwright/test/package.json"),
        "utf8",
      ),
    );
    expect(playwrightImage()).toBe(
      `mcr.microsoft.com/playwright:v${version}-noble`,
    );
  });

  it("is the same image the CI web job runs in", () => {
    expect(workflow).toContain(`image: ${playwrightImage()}`);
  });

  it("keeps the required check name `web`", () => {
    expect(workflow).toMatch(/^ {2}web:$/m);
  });
});
