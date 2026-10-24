import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SECTION_HEADINGS = [
  "Bring the news the model hasn't seen",
  "The model does the maths. The agent does the words.",
  "All 18 clubs, every matchday",
  "Close to the market, and honest about it",
  "Free to look. Pro to talk all day.",
  "Before you ask",
];

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByText("Matches scored live this season")).toBeVisible();
}

test.describe("landing page", () => {
  test.use({ reducedMotion: "reduce" });

  test("shows the hero and every section to an anonymous visitor", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "BundesPredict" })).toBeVisible();
    for (const heading of SECTION_HEADINGS) {
      await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
    }
    await expect(page.getByRole("link", { name: "Try the demo" }).first()).toBeVisible();
  });

  test("redirects a signed-in visitor to the matchday", async ({ page, context }) => {
    await context.addCookies([{ name: "bp_mock_plan", value: "free", domain: "localhost", path: "/" }]);
    await page.goto("/");
    await expect(page).toHaveURL(/\/matchday$/);
  });

  test("sends Start free to the login page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("main").getByRole("link", { name: "Start free" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("starts the demo from Try the demo and lands on the matchday", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("main").getByRole("link", { name: "Try the demo" }).click();
    await expect(page).toHaveURL(/\/matchday$/);
  });

  test("links the legal pages from the footer", async ({ page }) => {
    await page.goto("/");
    const footer = page.getByRole("contentinfo");
    for (const [link, heading] of [
      ["Terms", "Terms of use"],
      ["Privacy", "Privacy policy"],
      ["Refunds", "Refund policy"],
    ] as const) {
      await footer.getByRole("link", { name: link, exact: true }).click();
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await page.goBack();
    }
  });

  test("shows one FAQ answer at a time", async ({ page }) => {
    await page.goto("/");
    const source = page.getByRole("button", { name: "Where do the numbers come from?" });
    await source.click();
    await expect(source).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("button", { name: "Is this betting advice?" })).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#faq").getByRole("region")).toHaveCount(1);
  });

  test("replays the recorded example and ends on the adjusted odds", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Replay" }).click();
    await expect(page.getByText("Answered with 3 steps")).toBeVisible();
    await expect(page.getByRole("img", { name: /^Dortmund 53%, draw 27%, Hoffenheim 20%$/ })).toBeVisible();
  });

  test("looks right", async ({ page }) => {
    await page.goto("/");
    await settle(page);
    await expect(page).toHaveScreenshot("landing.png", { fullPage: true });
  });

  test("has no axe violations", async ({ page }) => {
    await page.goto("/");
    await settle(page);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});

test.describe("landing page with motion", () => {
  test("runs the hero canvas and the island follows the sections", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("section#hero canvas").first()).toBeAttached();
    await page.locator("#pricing").scrollIntoViewIfNeeded();
    await expect(page.locator("nav.island .isl-live").first()).toHaveText(/Pricing/);
  });
});

test.describe("how it's built", () => {
  test.use({ reducedMotion: "reduce" });

  test("draws the architecture and links to the source", async ({ page }) => {
    await page.goto("/how-its-built");
    await expect(page.getByRole("heading", { level: 1, name: "How it's built" })).toBeVisible();
    await expect(page.getByRole("img", { name: "BundesPredict architecture" })).toBeVisible();
    await expect(page.getByRole("link", { name: "The repository on GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/egeyesss/BundesPredict",
    );
    await expect(page.getByRole("link", { name: "The backtest report" })).toHaveAttribute("href", /reports\/backtest_report\.md$/);
  });

  test("looks right", async ({ page }) => {
    await page.goto("/how-its-built");
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("how-its-built.png", { fullPage: true });
  });

  test("has no axe violations", async ({ page }) => {
    await page.goto("/how-its-built");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });
});

test.describe("legal pages", () => {
  test.use({ reducedMotion: "reduce" });

  for (const path of ["terms", "privacy", "refunds"]) {
    test(`/legal/${path} names the contact address and has no axe violations`, async ({ page }) => {
      await page.goto(`/legal/${path}`);
      await expect(page.getByRole("link", { name: "bundespredict@egeyesilyurt.ca" }).first()).toBeVisible();
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    });
  }

  test("privacy lists every processor", async ({ page }) => {
    await page.goto("/legal/privacy");
    for (const name of ["Neon", "Railway", "Vercel", "Resend", "Stripe", "Anthropic", "Sentry"]) {
      await expect(page.getByRole("listitem").filter({ hasText: name }).first()).toBeVisible();
    }
  });
});

test.describe("metadata", () => {
  test("serves robots, sitemap and a share image", async ({ request }) => {
    expect(await (await request.get("/robots.txt")).text()).toContain("Sitemap: https://bundespredict.egeyesilyurt.ca/sitemap.xml");
    expect(await (await request.get("/sitemap.xml")).text()).toContain("/how-its-built");
    const image = await request.get("/opengraph-image");
    expect(image.headers()["content-type"]).toBe("image/png");
  });

  test("the landing page points at the share image", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /opengraph-image/);
    await expect(page).toHaveTitle(/BundesPredict \| Bundesliga win probabilities/);
  });
});
