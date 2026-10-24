import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

test.use({ timezoneId: "America/Toronto", locale: "en-US", reducedMotion: "reduce" });

async function signInAs(context: BrowserContext, plan: string) {
  await context.addCookies([{ name: "bp_mock_plan", value: plan, domain: "localhost", path: "/" }]);
}

async function settled(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".island-wrap:not([data-preview]) nav.island")).toHaveAttribute("data-ready", "true");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test.describe("/admin", () => {
  test("an admin sees the tiles, charts and tables", async ({ page, context }) => {
    await signInAs(context, "admin");
    await page.goto("/admin");
    await settled(page);

    const tiles = page.getByRole("region", { name: "Key numbers" });
    await expect(tiles).toContainText("Pro subscribers");
    await expect(page.getByRole("region", { name: "Test-mode subscriptions" })).toContainText("Test mode");
    await expect(page.getByRole("img", { name: /Chats per day by plan/ })).toBeVisible();
    await expect(page.getByRole("table", { name: "Recent Stripe webhook events" })).toContainText("failed");
    await expect(page.getByText("Read-only demo view.")).toHaveCount(0);
    await expect(page).toHaveScreenshot("admin-dashboard.png", { fullPage: true });
  });

  test("hovering a bar opens its tooltip", async ({ page, context }) => {
    await signInAs(context, "admin");
    await page.goto("/admin?days=7");
    await settled(page);

    const chart = page.getByRole("img", { name: /Chats per day by plan/ });
    await chart.scrollIntoViewIfNeeded();
    const box = (await chart.boundingBox())!;
    await page.mouse.move(box.x + box.width - 30, box.y + box.height / 2);

    await expect(page.getByRole("status").filter({ hasText: "chats" })).toContainText("Pro");
  });

  test("a demo viewer sees masked emails and the read-only note", async ({ page, context }) => {
    await signInAs(context, "demo");
    await page.goto("/admin");
    await settled(page);

    await expect(page.getByText("Read-only demo view.")).toBeVisible();
    await expect(page.getByText("a•••@example.com")).toBeVisible();
    await expect(page.getByText("a.keller@example.com")).toHaveCount(0);
    await expect(page).toHaveScreenshot("admin-demo.png", { fullPage: true });
  });

  test("everyone else gets the 404 page and signed-out visitors the login page", async ({ page, context, request }) => {
    const signedOut = await request.get("/admin", { maxRedirects: 0 });
    expect(signedOut.status()).toBe(307);
    expect(signedOut.headers()["location"]).toContain("/login?next=%2Fadmin");

    await signInAs(context, "free");
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "That page isn't on the team sheet" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Dashboard" })).toHaveCount(0);
  });

  test("has no axe violations", async ({ page, context }) => {
    await signInAs(context, "admin");
    await page.goto("/admin");
    await settled(page);

    const { violations } = await new AxeBuilder({ page }).analyze();
    expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  });
});
