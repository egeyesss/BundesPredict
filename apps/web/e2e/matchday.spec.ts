import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.use({ timezoneId: "America/Toronto", locale: "en-US" });

test.describe("matchday", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/matchday");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Matchday 8");
    await page.evaluate(() => document.fonts.ready);
  });

  test("lists every fixture with crests, odds and xG", async ({ page }) => {
    const cards = page.getByRole("article");
    await expect(cards).toHaveCount(9);

    const frankfurt = page.getByRole("article", { name: "Frankfurt v Köln" });
    await expect(frankfurt.getByRole("img", { name: "Eintracht Frankfurt" })).toBeVisible();
    await expect(frankfurt.getByRole("img", { name: "1.FC Köln" })).toBeVisible();
    await expect(frankfurt.getByRole("img", { name: "Frankfurt 52%, draw 27%, Köln 21%" })).toBeVisible();
    await expect(frankfurt).toContainText("xG 1.63 – 0.94");
  });

  test("shows kickoff in the viewer's timezone", async ({ page }) => {
    const frankfurt = page.getByRole("article", { name: "Frankfurt v Köln" });
    await expect(frankfurt.locator("time")).toHaveText(/Fri.*2:30 PM/);
  });

  test("asking about a match opens the chat pinned to that fixture", async ({ page }) => {
    const dortmund = page.getByRole("article", { name: "Dortmund v Hoffenheim" });
    await dortmund.getByRole("link", { name: "Ask about this match" }).click();

    await expect(page).toHaveURL(/\/chat\?fixture=803$/);
    const pinned = page.getByRole("region", { name: "Pinned fixture" });
    await expect(pinned).toContainText("Dortmund");
    await expect(pinned).toContainText("Hoffenheim");
    await expect(pinned).toContainText("Model");
  });

  test("has no axe violations", async ({ page }) => {
    // Mid fade-in, axe reads the cards' text as a blend with the background and reports contrast.
    await page.waitForFunction(() =>
      document
        .getAnimations()
        .filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity)
        .every((animation) => animation.playState !== "running"),
    );
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});

test.describe("matchday in another timezone", () => {
  test.use({ timezoneId: "Europe/Berlin" });

  test("moves the kickoff with the viewer", async ({ page }) => {
    await page.goto("/matchday");
    const frankfurt = page.getByRole("article", { name: "Frankfurt v Köln" });
    await expect(frankfurt.locator("time")).toHaveText(/Fri.*8:30 PM/);
  });
});

test.describe("matchday visuals", () => {
  test.use({ reducedMotion: "reduce" });

  test("matches the visual snapshot", async ({ page }) => {
    await page.goto("/matchday");
    await expect(page.getByRole("article")).toHaveCount(9);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => [...document.images].every((image) => image.complete));
    await expect(page.locator("main")).toHaveScreenshot("matchday.png");
  });
});

test("the home page sends visitors to the matchday", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/matchday$/);
});
