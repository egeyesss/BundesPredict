import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.describe("track record", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/track-record");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("How the model has done");
    await page.evaluate(() => document.fonts.ready);
  });

  test("separates the live record from the backtest", async ({ page }) => {
    await expect(page.getByText("Live since 28 Aug 2026")).toBeVisible();
    await expect(page.getByText("0.2086")).toBeVisible();

    await page.getByRole("tab", { name: "Backtest · 5 seasons" }).click();

    const panel = page.getByRole("tabpanel", { name: "Backtest · 5 seasons" });
    await expect(panel.getByText("1,827")).toBeVisible();
    await expect(panel.getByRole("img", { name: /Ranked probability score by forecaster/ })).toBeVisible();
  });

  test("draws the RPS chart and offers the same numbers as a table", async ({ page }) => {
    const card = page.getByRole("region", { name: "Average RPS per matchday" });
    await expect(card.getByRole("img", { name: /Average ranked probability score per matchday/ })).toBeVisible();

    await card.getByRole("button", { name: "Show as table" }).click();

    await expect(card.getByRole("row")).toHaveCount(8);
  });

  test("has no axe violations", async ({ page }) => {
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});

test.describe("track record visuals", () => {
  test("live tab", async ({ page }) => {
    await page.goto("/track-record");
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole("img", { name: /Average ranked probability score/ })).toBeVisible();
    await expect(page).toHaveScreenshot("live.png", { fullPage: true });
  });

  test("backtest tab", async ({ page }) => {
    await page.goto("/track-record");
    await page.getByRole("tab", { name: "Backtest · 5 seasons" }).click();
    await expect(page.getByRole("img", { name: /Ranked probability score by forecaster/ })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("backtest.png", { fullPage: true });
  });
});
