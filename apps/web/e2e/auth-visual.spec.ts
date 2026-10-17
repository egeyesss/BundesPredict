import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

test.use({ timezoneId: "America/Toronto", locale: "en-US", reducedMotion: "reduce" });

type Plan = "free" | "pro" | "cancelling" | "pastdue";

async function signInAs(context: BrowserContext, plan: Plan) {
  await context.addCookies([{ name: "bp_mock_plan", value: plan, domain: "localhost", path: "/" }]);
}

async function settled(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".island-wrap:not([data-preview]) nav.island")).toHaveAttribute("data-ready", "true");
}

const shot = (page: Page, name: string) => expect(page).toHaveScreenshot(name, { fullPage: true });

test.describe("login", () => {
  test("email step", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Sign in to talk to the agent" })).toBeVisible();
    await settled(page);
    await shot(page, "login-email.png");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });

  test("create account mode with a validation error", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "New here? Create an account" }).click();
    await page.getByLabel("Email", { exact: true }).fill("nope");
    await page.getByRole("button", { name: "Email me a code" }).click();
    await expect(page.getByText("That doesn't look like an email address")).toBeVisible();
    await settled(page);
    await shot(page, "login-signup-error.png");
  });

  test("code step", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email", { exact: true }).fill("sam.rivera@example.com");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();
    await expect(page.getByRole("heading", { name: "Enter the 8-letter code" })).toBeVisible();
    await page.keyboard.type("BCDF");
    await settled(page);
    await shot(page, "login-code.png");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });

  test("wrong code", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email", { exact: true }).fill("sam.rivera@example.com");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();
    await expect(page.getByRole("heading", { name: "Enter the 8-letter code" })).toBeVisible();
    await page.keyboard.type("ZZZZZZZZ");
    await expect(page.getByText("That code didn't work")).toBeVisible();
    await settled(page);
    await shot(page, "login-code-error.png");
  });

  test("Google sign-in failed", async ({ page }) => {
    await page.goto("/login?error=social");
    await expect(page.getByText("Google sign-in didn't finish")).toBeVisible();
    await settled(page);
    await shot(page, "login-social-error.png");
  });
});

test.describe("account", () => {
  for (const [plan, name] of [
    ["free", "account-free.png"],
    ["pro", "account-pro.png"],
    ["cancelling", "account-cancelling.png"],
    ["pastdue", "account-past-due.png"],
  ] as const) {
    test(`${plan} plan`, async ({ page, context }) => {
      await signInAs(context, plan);
      await page.goto("/account");
      await expect(page.getByRole("heading", { level: 1 })).toContainText("Sam Rivera");
      await settled(page);
      await shot(page, name);
    });
  }

  test("has no axe violations", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Sam Rivera");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });

  test("account menu open", async ({ page, context, viewport }) => {
    await signInAs(context, "free");
    await page.goto("/matchday");
    await settled(page);
    if ((viewport?.width ?? 0) < 800) {
      await page.getByRole("button", { name: "Open menu" }).click();
      await expect(page.getByRole("button", { name: "Close menu" })).toBeVisible();
    } else {
      await page.getByRole("button", { name: "Account menu" }).first().click();
      await expect(page.getByRole("menu")).toBeVisible();
    }
    await expect(page).toHaveScreenshot("account-menu.png");
  });

  test("checkout return while waiting", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account?checkout=success");
    await expect(page.getByRole("heading", { name: "Confirming your payment" })).toBeVisible();
    await settled(page);
    await shot(page, "checkout-waiting.png");
  });

  test("checkout return confirmed", async ({ page, context }) => {
    await signInAs(context, "pro");
    await page.goto("/account?checkout=success");
    await expect(page.getByRole("heading", { name: "You're on Pro" })).toBeVisible();
    await settled(page);
    await shot(page, "checkout-pro.png");
  });
});
