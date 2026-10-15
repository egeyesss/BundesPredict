import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

test.describe("styleguide", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/styleguide");
    await expect(page.locator('.island[data-ready="true"]').first()).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
    await page.waitForFunction(() => [...document.images].every((image) => image.complete));
  });

  test("matches the visual snapshot", async ({ page }) => {
    await expect(page).toHaveScreenshot("styleguide.png", { fullPage: true });
  });

  test("has no axe violations", async ({ page }) => {
    // axe walks every node of this long page, which is slow when CI runners are busy.
    test.setTimeout(180_000);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test("lists every design token with its value", async ({ page }) => {
    const swatches = page.locator("[data-token]");
    await expect(swatches.first()).toBeVisible();
    for (const token of ["--bp-bg", "--bp-red", "--bp-red-text", "--odds-win", "--odds-draw-lead", "--bp-up", "--bp-radius"]) {
      await expect(page.locator(`[data-token="${token}"]`)).toHaveCount(1);
    }
  });

  test("shows all 18 club crests and the missing-asset chip", async ({ page }) => {
    await expect(page.locator('[data-crest-row]')).toHaveCount(18);
    await expect(page.locator('[data-fallback="chip"]').first()).toBeVisible();
  });

  test("loads every crest image", async ({ page }) => {
    const broken = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLImageElement>("img")]
        .filter((img) => img.complete && img.naturalWidth === 0)
        .map((img) => img.src),
    );
    expect(broken).toEqual([]);
  });
});
