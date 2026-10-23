import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.use({ timezoneId: "America/Toronto", locale: "en-US", reducedMotion: "reduce" });

const shot = async (page: Page, name: string) => {
  await page.evaluate(() => document.fonts.ready);
  await expect(page).toHaveScreenshot(name, { fullPage: true });
};

test.describe("email unsubscribe", () => {
  test("asks first, then confirms", async ({ page }) => {
    await page.goto("/email/unsubscribe?t=signed-token");
    await expect(page.getByRole("heading", { name: "Stop the Thursday matchday email?" })).toBeVisible();
    await shot(page, "unsubscribe-ask.png");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

    await page.getByRole("button", { name: "Unsubscribe" }).click();
    await expect(page.getByRole("heading", { name: "You're unsubscribed" })).toBeVisible();
    await shot(page, "unsubscribe-done.png");
  });

  test("opening the link does not unsubscribe anyone", async ({ page }) => {
    const posts: string[] = [];
    page.on("request", (request) => request.method() === "POST" && posts.push(request.url()));
    await page.goto("/email/unsubscribe?t=signed-token");
    await expect(page.getByRole("button", { name: "Unsubscribe" })).toBeVisible();
    expect(posts).toEqual([]);
  });

  test("a bad link points at the account page", async ({ page }) => {
    await page.goto("/email/unsubscribe?t=invalid-link");
    await page.getByRole("button", { name: "Unsubscribe" }).click();
    await expect(page.getByRole("heading", { name: "This link doesn't work" })).toBeVisible();
    await shot(page, "unsubscribe-invalid.png");
  });

  test("a link without a token explains itself", async ({ page }) => {
    await page.goto("/email/unsubscribe");
    await expect(page.getByRole("heading", { name: "This link doesn't work" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Unsubscribe" })).toHaveCount(0);
  });
});
