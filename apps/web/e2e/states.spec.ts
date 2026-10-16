import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce", timezoneId: "America/Toronto", locale: "en-US" });

test.describe("states", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/styleguide/states");
    await expect(page.locator('[data-specimen="fixtures.empty"]')).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
  });

  test("names what broke and what to do in every error state", async ({ page }) => {
    const specimen = (name: string) => page.locator(`[data-specimen="${name}"]`);
    await expect(specimen("fixtures.error")).toContainText("Couldn't load this week's fixtures");
    await expect(specimen("fixtures.error")).toContainText("Your chats and account are fine.");
    await expect(specimen("agent.model_unavailable")).toContainText("This chat wasn't counted.");
    await expect(specimen("agent.model_unavailable").getByRole("button", { name: "Try again" })).toBeVisible();
    await expect(specimen("agent.rate_limited")).toContainText("You can send again in 24 s.");
    await expect(specimen("history.empty").getByRole("link", { name: "Go to matchday" })).toBeVisible();
  });

  test("skeletons are marked busy", async ({ page }) => {
    for (const name of ["fixtures.loading", "conversation.loading", "history.loading"]) {
      await expect(page.locator(`[data-specimen="${name}"] [aria-busy="true"]`)).toBeVisible();
    }
  });

  test("matches the visual snapshot", async ({ page }) => {
    await expect(page).toHaveScreenshot("states.png", { fullPage: true });
  });

  test("has no axe violations", async ({ page }) => {
    test.setTimeout(180_000);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});
