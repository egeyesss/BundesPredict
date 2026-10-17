import { expect, test, type BrowserContext, type Page } from "@playwright/test";

test.use({ timezoneId: "America/Toronto", locale: "en-US", reducedMotion: "reduce" });

const VALID_CODE = "BCDFGHJK";
const WRONG_CODE = "ZZZZZZZZ";

async function signInAs(context: BrowserContext, plan: "free" | "pro" | "cancelling" | "pastdue" | "demo") {
  await context.addCookies([{ name: "bp_mock_plan", value: plan, domain: "localhost", path: "/" }]);
}

/** Waits for the first slot to hold focus, so keystrokes never race the code step mounting. */
async function typeCode(page: Page, code: string) {
  await expect(page.getByRole("textbox", { name: "Character 1 of 8" })).toBeFocused();
  await page.keyboard.type(code);
}

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 0) < 800;

/** The desktop dropdown on wide screens, the burger menu on phones. */
async function openAccountMenu(page: Page) {
  if (isPhone(page)) await page.getByRole("button", { name: "Open menu" }).click();
  else await page.getByRole("button", { name: "Account menu" }).first().click();
}

const menuItemRole = (page: Page) => (isPhone(page) ? "button" : "menuitem");

const email = (page: Page) => page.getByLabel("Email", { exact: true });
const codeSlots = (page: Page) => page.getByRole("group", { name: "Sign-in code" });

test.describe("protected routes", () => {
  test("send a signed-out visitor to the login page and remember where they were going", async ({ page }) => {
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?next=%2Faccount$/);

    await page.goto("/chat?fixture=803");
    await expect(page).toHaveURL(/\/login\?next=%2Fchat%3Ffixture%3D803$/);
  });

  test("keep the next path through the account page's checkout return", async ({ page }) => {
    await page.goto("/account?checkout=success");
    await expect(page).toHaveURL(/\/login\?next=%2Faccount%3Fcheckout%3Dsuccess$/);
  });

  test("bounce a signed-in visitor off the login page", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/login");
    await expect(page).toHaveURL(/\/matchday$/);
  });
});

test.describe("email code sign-in", () => {
  test("signs in an existing user with a code and lands on the matchday", async ({ page }) => {
    await page.goto("/login");
    await email(page).fill("sam.rivera@example.com");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();

    await expect(page.getByRole("heading", { name: "Enter the 8-letter code" })).toBeVisible();
    await expect(page.getByText("sam.rivera@example.com")).toBeVisible();
    await typeCode(page, VALID_CODE);

    await expect(page.getByText("Signed in")).toBeVisible();
    await expect(page).toHaveURL(/\/matchday$/);
    await expect(page.locator("[data-plan='free']").first()).toBeAttached();
  });

  test("honours the next path after signing in", async ({ page }) => {
    await page.goto("/login?next=%2Faccount");
    await email(page).fill("sam.rivera@example.com");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();
    await expect(page.getByRole("heading", { name: "Enter the 8-letter code" })).toBeVisible();
    await typeCode(page, VALID_CODE);
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Sam Rivera");
  });

  test("signs up a new address with the same code step", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "New here? Create an account" }).click();
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
    await email(page).fill("new.person@example.com");
    await page.getByRole("button", { name: "Email me a code" }).click();

    await expect(page.getByRole("heading", { name: "Enter the 8-letter code" })).toBeVisible();
    await typeCode(page, VALID_CODE);
    await expect(page).toHaveURL(/\/matchday$/);
  });

  test("shows an error and clears the slots after a wrong code", async ({ page }) => {
    await page.goto("/login");
    await email(page).fill("sam.rivera@example.com");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();
    await typeCode(page, WRONG_CODE);

    await expect(page.getByText("That code didn't work")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
    await expect(codeSlots(page).getByRole("textbox").first()).toHaveValue("");
    await expect(codeSlots(page).getByRole("textbox").first()).toBeFocused();
  });

  test("rejects an address that is not an email without calling the server", async ({ page }) => {
    await page.goto("/login");
    await email(page).fill("not-an-email");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();
    await expect(page.getByText("That doesn't look like an email address")).toBeVisible();
    await expect(email(page)).toHaveAttribute("aria-invalid", "true");
  });

  test("lets the user go back and use a different email", async ({ page }) => {
    await page.goto("/login");
    await email(page).fill("sam.rivera@example.com");
    await page.getByRole("button", { name: "Email me a sign-in code" }).click();
    await page.getByRole("button", { name: "Use a different email" }).click();
    await expect(page.getByRole("heading", { name: "Sign in to talk to the agent" })).toBeVisible();
    await expect(email(page)).toHaveValue("sam.rivera@example.com");
  });
});

test.describe("Google sign-in", () => {
  test("posts a real form to the provider redirect with the callback and process", async ({ page }) => {
    await page.goto("/login?next=%2Faccount");
    // The mock service worker owns this origin, so the request is observed rather than fulfilled.
    const posted = page.waitForRequest((request) => request.method() === "POST" && request.url().endsWith("/_allauth/browser/v1/auth/provider/redirect"));
    await page.getByRole("button", { name: "Continue with Google" }).click();

    const form = new URLSearchParams((await posted).postData() ?? "");
    expect(form.get("provider")).toBe("google");
    expect(form.get("callback_url")).toBe("/account");
    expect(form.get("process")).toBe("login");
    expect(form.get("csrfmiddlewaretoken")).toBeTruthy();
  });

  test("explains a failed Google sign-in", async ({ page }) => {
    await page.goto("/login?error=social");
    await expect(page.getByRole("alert").filter({ hasText: "Google sign-in" })).toContainText("didn't finish");
  });
});

test.describe("sign out", () => {
  test("from the account page returns to the login page", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account");
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?next=/);
  });

  test("from the account menu", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/matchday");
    await openAccountMenu(page);
    await page.getByRole(menuItemRole(page), { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe("account menu", () => {
  test("shows the plan pill, today's chats and the right billing action", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/matchday");
    await expect(page.locator("nav [data-plan='free']").first()).toBeAttached();
    await openAccountMenu(page);
    await expect(page.getByRole(isPhone(page) ? "navigation" : "menu").getByText("2 of 3 free chats left today")).toBeVisible();
    await expect(page.getByRole(menuItemRole(page), { name: /Upgrade to Pro/ })).toBeVisible();
  });

  test("offers Manage billing to a Pro user", async ({ page, context }) => {
    await signInAs(context, "pro");
    await page.goto("/matchday");
    await openAccountMenu(page);
    await expect(page.getByRole(menuItemRole(page), { name: /Manage billing/ })).toBeVisible();
  });

  test("shows Sign in when signed out", async ({ page }) => {
    await page.goto("/matchday");
    if (isPhone(page)) await page.getByRole("button", { name: "Open menu" }).click();
    await expect(page.getByRole("link", { name: "Sign in" }).filter({ visible: true }).first()).toBeVisible();
  });
});

test.describe("billing", () => {
  test("Upgrade sends a free user to Stripe Checkout", async ({ page, context }) => {
    await page.route("https://checkout.stripe.com/**", (route) =>
      route.fulfill({ contentType: "text/html", body: "<title>Stripe Checkout</title>" }),
    );
    await signInAs(context, "free");
    await page.goto("/account");
    await page.getByRole("button", { name: "Upgrade to Pro" }).click();
    await expect(page).toHaveURL(/^https:\/\/checkout\.stripe\.com\//);
  });

  test("Manage billing opens the Stripe portal for a Pro user", async ({ page, context }) => {
    await page.route("https://billing.stripe.com/**", (route) =>
      route.fulfill({ contentType: "text/html", body: "<title>Stripe Portal</title>" }),
    );
    await signInAs(context, "pro");
    await page.goto("/account");
    await page.getByRole("button", { name: "Manage billing" }).click();
    await expect(page).toHaveURL(/^https:\/\/billing\.stripe\.com\//);
  });

  test("the checkout return never shows Pro until /me says so", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account?checkout=success");
    await expect(page.getByRole("heading", { name: "Confirming your payment" })).toBeVisible();

    // Several polls go by with the webhook still outstanding.
    await page.waitForTimeout(5_000);
    await expect(page.getByRole("heading", { name: "Confirming your payment" })).toBeVisible();
    await expect(page.getByText("You're on Pro")).toHaveCount(0);
    await expect(page.locator("[data-plan='pro']")).toHaveCount(0);

    await signInAs(context, "pro");
    await expect(page.getByRole("heading", { name: "You're on Pro" })).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("[data-plan='pro']").first()).toBeVisible();
  });

  test("says so plainly when Stripe is slow", async ({ page, context }) => {
    await page.clock.install();
    await signInAs(context, "free");
    await page.goto("/account?checkout=success");
    await expect(page.getByRole("heading", { name: "Confirming your payment" })).toBeVisible();
    await page.clock.fastForward(21_000);
    await expect(page.getByRole("heading", { name: "Still waiting on Stripe" })).toBeVisible();
    await expect(page.getByText("You're on Pro")).toHaveCount(0);
  });
});

test.describe("account page", () => {
  test("shows the free plan, today's usage and the upgrade call to action", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Sam Rivera");
    await expect(page.getByRole("main").getByText("2 of 3 free chats left")).toBeVisible();
    await expect(page.getByRole("button", { name: "Upgrade to Pro" })).toBeVisible();
  });

  test("shows the renewal date for Pro and the end date once cancelled", async ({ page, context }) => {
    await signInAs(context, "pro");
    await page.goto("/account");
    await expect(page.getByText(/Renews on Nov 2/)).toBeVisible();

    await signInAs(context, "cancelling");
    await page.goto("/account");
    await expect(page.getByText(/Pro stays on until Nov 2/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Keep Pro" })).toBeVisible();
  });

  test("warns about a failed payment", async ({ page, context }) => {
    await signInAs(context, "pastdue");
    await page.goto("/account");
    await expect(page.getByRole("alert").filter({ hasText: "last payment" })).toContainText("didn't go through");
    await expect(page.getByRole("button", { name: "Update card" })).toBeVisible();
  });

  test("saves the email opt-in toggle through PATCH /me", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account");
    const toggle = page.getByRole("switch", { name: "Thursday matchday email" });
    await expect(toggle).not.toBeChecked();
    const patch = page.waitForRequest((request) => request.method() === "PATCH" && request.url().endsWith("/api/v1/me"));
    await toggle.click();
    expect((await patch).postDataJSON()).toEqual({ email_opt_in: true });
    await expect(toggle).toBeChecked();
  });

  test("pins a manually chosen time zone", async ({ page, context }) => {
    await signInAs(context, "free");
    await page.goto("/account");
    const patch = page.waitForRequest((request) => request.method() === "PATCH" && request.url().endsWith("/api/v1/me"));
    await page.getByRole("combobox", { name: "Time zone" }).selectOption("Europe/Berlin");
    expect((await patch).postDataJSON()).toEqual({ timezone: "Europe/Berlin", timezone_source: "manual" });
    await expect(page.getByRole("combobox", { name: "Time zone" })).toHaveValue("Europe/Berlin");
  });
});
