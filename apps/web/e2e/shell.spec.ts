import { expect, test } from "@playwright/test";

const island = (page: import("@playwright/test").Page) => page.locator(".island-wrap:not([data-preview]) nav.island");

test.describe("app shell", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/styleguide");
    await expect(island(page)).toHaveAttribute("data-ready", "true");
    await page.evaluate(() => document.fonts.ready);
  });

  test("footer carries the disclaimer, the league mark and the credit link", async ({ page }) => {
    const footer = page.getByRole("contentinfo");
    await expect(footer).toContainText("not affiliated with, endorsed by or sponsored by DFL Deutsche Fußball Liga");
    await expect(footer).toContainText("Not betting advice");
    await expect(footer.getByRole("img", { name: "Bundesliga" })).toBeVisible();
    await expect(footer.getByRole("link", { name: "Rare UI" })).toHaveAttribute("href", "https://www.rareui.com");
  });

  test("skip link moves focus to the main content", async ({ page }) => {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
  });
});

test.describe("island on desktop", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) < 800, "desktop layouts");
  test.use({ reducedMotion: "reduce" });

  test.beforeEach(async ({ page }) => {
    await page.goto("/styleguide");
    await expect(island(page)).toHaveAttribute("data-ready", "true");
    await page.evaluate(() => document.fonts.ready);
  });

  test("is full at the top, compact when scrolled, full again on hover", async ({ page }) => {
    await expect(island(page)).toHaveAttribute("data-mode", "full");
    await expect(island(page)).toHaveScreenshot("island-full.png");

    await page.mouse.wheel(0, 900);
    await expect(island(page)).toHaveAttribute("data-mode", "compact");
    await expect(island(page)).toHaveScreenshot("island-compact.png");

    await island(page).hover();
    await expect(island(page)).toHaveAttribute("data-mode", "full");
  });

  test("keyboard focus expands a compact island", async ({ page }) => {
    await page.mouse.wheel(0, 900);
    await expect(island(page)).toHaveAttribute("data-mode", "compact");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await expect(island(page)).toHaveAttribute("data-mode", "full");
  });

  test("clicking the wordmark scrolls to the top", async ({ page }) => {
    await page.goto("/matchday");
    await expect(island(page)).toHaveAttribute("data-ready", "true");
    await page.evaluate(() => {
      document.body.style.minHeight = "3000px";
      window.scrollTo(0, 1500);
    });
    await expect(island(page)).toHaveAttribute("data-mode", "compact");
    await island(page).getByRole("link", { name: "BundesPredict home" }).first().click({ force: true });
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  });
});

test.describe("island on a phone", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) >= 800, "mobile layouts");
  test.use({ reducedMotion: "reduce" });

  test.beforeEach(async ({ page }) => {
    await page.goto("/styleguide");
    await expect(island(page)).toHaveAttribute("data-ready", "true");
    await page.evaluate(() => document.fonts.ready);
  });

  test("uses the mobile layout and opens the menu without shifting sideways", async ({ page }) => {
    await expect(island(page)).toHaveAttribute("data-mode", "mobile");
    await expect(island(page)).toHaveScreenshot("island-mobile.png");

    await island(page).getByRole("button", { name: "Open menu" }).click();
    await expect(island(page)).toHaveAttribute("data-mode", "open");
    await expect(island(page).getByRole("button", { name: "Close menu" })).toBeFocused();
    expect(await island(page).evaluate((element) => element.scrollLeft)).toBe(0);
    await expect(island(page)).toHaveScreenshot("island-open.png");
  });

  test("Escape closes the menu and returns focus to the burger", async ({ page }) => {
    await island(page).getByRole("button", { name: "Open menu" }).click();
    await page.keyboard.press("Escape");
    await expect(island(page)).toHaveAttribute("data-mode", "mobile");
    await expect(island(page).getByRole("button", { name: "Open menu" })).toBeFocused();
  });

  test("tapping the scrim closes the menu", async ({ page }) => {
    await island(page).getByRole("button", { name: "Open menu" }).click();
    await page.mouse.click(10, 700);
    await expect(island(page)).toHaveAttribute("data-mode", "mobile");
  });
});

test.describe("motion preferences", () => {
  test("island transitions are off under reduced motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/styleguide");
    const duration = await island(page).evaluate((element) => getComputedStyle(element).transitionDuration);
    expect(duration.split(",").every((value) => parseFloat(value) === 0)).toBe(true);
  });

  test("island springs are on when motion is allowed", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto("/styleguide");
    const duration = await island(page).evaluate((element) => getComputedStyle(element).transitionDuration);
    expect(parseFloat(duration.split(",")[0])).toBeGreaterThan(0.3);
  });
});
