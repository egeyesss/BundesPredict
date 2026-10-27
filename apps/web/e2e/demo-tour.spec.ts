import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.use({ reducedMotion: "reduce", timezoneId: "America/Toronto", locale: "en-US" });

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 0) < 640;

// The mock demo expires 24 hours after the browser clock, so a fixed clock fixes the banner countdown.
test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-10-26T12:00:00Z"));
});

/** The data-tour anchor each stop should spotlight, in tour order. */
const ANCHORS = ["fixture", "bar", "xg", "ask", "composer", "steps", "result", "chips", "quota", "upgrade", "rps", "edge", "mrr", "cost", "webhooks"];
const PATHS = [...Array(4).fill("/matchday"), ...Array(6).fill("/chat"), ...Array(2).fill("/track-record"), ...Array(3).fill("/admin")];
const SCREENS = [...Array(4).fill("Matchday"), ...Array(6).fill("Chat"), ...Array(2).fill("Track record"), ...Array(3).fill("Admin")];

const bubble = (page: Page) => page.getByRole("dialog");
const next = (page: Page) => bubble(page).getByRole("button", { name: /^(Next|Finish)$/ });

async function startFromLanding(page: Page) {
  await page.goto("/");
  await page.getByRole("main").getByRole("link", { name: "Try the demo" }).click();
  await expect(page).toHaveURL(/\/matchday$/);
  await expect(page.getByRole("dialog", { name: "Take the tour" })).toBeVisible();
}

/** Where the first visible, un-inert element with this anchor is on screen. */
function anchorBox(page: Page, name: string) {
  return page.evaluate((anchor) => {
    const found = [...document.querySelectorAll<HTMLElement>(`[data-tour="${anchor}"]`)].find((el) => el.getClientRects().length > 0 && !el.closest("[inert]"));
    if (!found) return null;
    const { x, y, width, height } = found.getBoundingClientRect();
    return { x, y, width, height };
  }, name);
}

/** Waits until the spotlight has settled on the stop's anchor, then checks the bubble is fully on screen and not under the demo bar. */
async function expectSpotlightOn(page: Page, name: string) {
  const spot = page.locator(".tour-spot");
  await expect
    .poll(
      async () => {
        const [anchor, hole] = [await anchorBox(page, name), await spot.boundingBox()];
        if (!anchor || !hole) return "no anchor or spotlight yet";
        const off = [hole.x - (anchor.x - 8), hole.y - (anchor.y - 8), hole.width - (anchor.width + 16), hole.height - (anchor.height + 16)].map(Math.abs);
        return Math.max(...off) < 3 ? "on target" : `off by ${off.join(", ")}`;
      },
      { timeout: 20_000 },
    )
    .toBe("on target");

  const box = await bubble(page).boundingBox();
  const viewport = page.viewportSize()!;
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
  const covered = await bubble(page).evaluate((element) => {
    const { x, y, width, height } = element.getBoundingClientRect();
    const top = document.elementFromPoint(x + width / 2, y + height / 2);
    return top === null || !element.contains(top);
  });
  expect(covered, "something sits on top of the bubble").toBe(false);
}

/** Waits until the anchor has stopped moving, so a screenshot never catches a late scroll or the typed answer growing. */
async function expectStill(page: Page, name: string) {
  await expect
    .poll(
      async () => {
        // The tour re-aligns for up to 4s after an anchor appears, because late layout can push it off screen.
        const before = JSON.stringify(await anchorBox(page, name));
        await page.waitForTimeout(4500);
        return before === JSON.stringify(await anchorBox(page, name));
      },
      { timeout: 20_000 },
    )
    .toBe(true);
}

async function waitForStop(page: Page, index: number) {
  await expect(bubble(page)).toContainText(`${index + 1} of 15 · ${SCREENS[index]}`);
  await expect(page).toHaveURL(new RegExp(`${PATHS[index]}(\\?.*)?$`));
}

test.describe("the guided demo", () => {
  test("goes from the landing page through all 15 stops, with a recorded answer in the chat", async ({ page }) => {
    await startFromLanding(page);
    await expect(page.getByRole("region", { name: "Demo mode" })).toContainText("payments use Stripe test cards, nothing is charged");
    await expect(page.getByRole("timer")).toHaveText("24:00:00");
    await expect(page).toHaveScreenshot("demo-welcome.png");

    await page.getByRole("button", { name: "Take the tour" }).click();
    const screenshotAt = new Map([
      [1, "demo-stop-matchday.png"],
      [6, "demo-stop-chat.png"],
      [10, "demo-stop-track-record.png"],
      [12, "demo-stop-admin.png"],
    ]);

    for (let index = 0; index < 15; index++) {
      await waitForStop(page, index);
      if (index === 4) {
        await expect(page.getByRole("textbox", { name: "Message" })).toHaveValue(/^Suppose .+'s main striker is out\./);
        await expect(bubble(page)).toContainText("Uses 1 of your 10 demo chats");
      }
      if (index === 5) await expect(page.getByText("Recorded example, not a live answer")).toBeVisible();
      await expectSpotlightOn(page, ANCHORS[index]);
      const name = screenshotAt.get(index);
      if (name) {
        await expectStill(page, ANCHORS[index]);
        // The 375px chat stop shifts a few rows of the answer behind the dim layer between runs, so it gets a wider pixel budget.
        await expect(page).toHaveScreenshot(name, { maxDiffPixelRatio: name === "demo-stop-chat.png" ? 0.06 : 0.002 });
      }
      await next(page).click();
    }

    await expect(bubble(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Explain: Payments that can't double-count" })).toBeVisible();
  });

  test("sends the suggested message as a real chat that counts toward the 10", async ({ page }) => {
    await startFromLanding(page);
    await page.getByRole("button", { name: "Take the tour" }).click();
    for (let index = 0; index < 4; index++) await next(page).click();
    await waitForStop(page, 4);

    await bubble(page).getByRole("button", { name: "Send this message" }).click();
    await expect(bubble(page)).toContainText("Sent. Press Next");
    await next(page).click();
    await waitForStop(page, 5);
    await expectSpotlightOn(page, "steps");
    await expect(page.getByText("Recorded example, not a live answer")).toHaveCount(0);

    await next(page).click();
    await waitForStop(page, 6);
    await expectSpotlightOn(page, "result");
    await next(page).click();
    await next(page).click();
    await waitForStop(page, 8);
    await expectSpotlightOn(page, "quota");
    await expect(page.getByText("9 of 10 demo chats left")).toBeVisible();
  });

  test("keeps the question-mark hotspots after Skip, each opening only its own stop", async ({ page }) => {
    await startFromLanding(page);
    await page.getByRole("button", { name: "Take the tour" }).click();
    await bubble(page).getByRole("button", { name: "Skip tour" }).click();
    await expect(bubble(page)).toHaveCount(0);

    const hotspot = page.getByRole("button", { name: "Explain: Expected goals" });
    await expect(hotspot).toBeVisible();
    await hotspot.click();
    await expect(bubble(page)).toContainText("Quick tip");
    await expect(bubble(page)).toContainText("Expected goals");
    await expectSpotlightOn(page, "xg");
    await page.keyboard.press("Escape");
    await expect(bubble(page)).toHaveCount(0);
    await expect(hotspot).toBeFocused();

    await page.getByRole("button", { name: "Restart the tour" }).click();
    await expect(page.getByRole("dialog", { name: "Take the tour" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Explain:/ })).toHaveCount(0);
  });

  test("resumes where it was after a reload and moves with the arrow keys", async ({ page }) => {
    await startFromLanding(page);
    await page.getByRole("button", { name: "Take the tour" }).click();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await waitForStop(page, 2);
    await page.reload();
    await waitForStop(page, 2);
    await page.keyboard.press("ArrowLeft");
    await waitForStop(page, 1);
  });

  test("the demo bar leaves the island, the composer and the bubble uncovered", async ({ page }) => {
    await startFromLanding(page);
    await page.getByRole("button", { name: "Look around first" }).click();
    const banner = page.getByRole("region", { name: "Demo mode" });
    const island = page.locator(".island-wrap:not([data-preview]) nav.island");
    const [bannerBox, islandBox] = [await banner.boundingBox(), await island.boundingBox()];
    expect(bannerBox!.y + bannerBox!.height).toBeLessThanOrEqual(islandBox!.y);

    await page.goto("/chat?fixture=803");
    const composer = page.getByRole("textbox", { name: "Message" });
    await expect(composer).toBeVisible();
    const box = await composer.boundingBox();
    expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
    const covered = await composer.evaluate((element) => {
      const { x, y, width, height } = element.getBoundingClientRect();
      const top = document.elementFromPoint(x + width / 2, y + height / 2);
      return top === null || !(element === top || element.contains(top));
    });
    expect(covered).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  });

  test("docks the bubble as a bottom sheet under 640px", async ({ page }) => {
    test.skip(!isPhone(page), "phone only");
    await startFromLanding(page);
    await page.getByRole("button", { name: "Take the tour" }).click();
    await waitForStop(page, 0);
    await expectSpotlightOn(page, "fixture");
    await expect(bubble(page)).toHaveAttribute("data-side", "sheet");
    const box = await bubble(page).boundingBox();
    expect(box!.y + box!.height).toBeGreaterThan(page.viewportSize()!.height - 20);
    await expect(page).toHaveScreenshot("demo-sheet-375.png");
  });

  test("keeps the tab order inside the bubble and gives focus back on Escape", async ({ page }) => {
    await startFromLanding(page);
    await page.getByRole("button", { name: "Take the tour" }).click();
    await page.keyboard.press("ArrowRight");
    for (let press = 0; press < 6; press++) {
      await page.keyboard.press("Tab");
      expect(await bubble(page).evaluate((element) => element.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(bubble(page)).toHaveCount(0);
  });
});

test.describe("accessibility and motion", () => {
  test("has no axe violations on the welcome card, a stop, or the hotspots", async ({ page }) => {
    await startFromLanding(page);
    await page.evaluate(() => document.fonts.ready);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

    await page.getByRole("button", { name: "Take the tour" }).click();
    await waitForStop(page, 0);
    await expectSpotlightOn(page, "fixture");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

    await bubble(page).getByRole("button", { name: "Skip tour" }).click();
    await expect(page.getByRole("button", { name: "Explain: One card per fixture" })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });

  test("moves the spotlight on a spring only when reduced motion is off", async ({ page }) => {
    const springy = () => page.locator(".tour-spot").evaluate((element) => getComputedStyle(element).transitionDuration);
    await startFromLanding(page);
    await page.getByRole("button", { name: "Take the tour" }).click();
    await waitForStop(page, 0);
    await expectSpotlightOn(page, "fixture");
    expect(await springy()).toBe("0s");

    await page.emulateMedia({ reducedMotion: "no-preference" });
    await expect.poll(springy).toBe("0.38s, 0.38s, 0.38s, 0.38s");
    await page.keyboard.press("ArrowRight");
    await waitForStop(page, 1);
    await expectSpotlightOn(page, "bar");
  });
});

test.describe("when a demo cannot be started", () => {
  for (const [variant, title, message] of [
    ["ip_limit", "Too many demos from this network today", "This network has started its 3 demos for today."],
    ["budget", "Today's demo spots are taken", "Today's demo spots are used up."],
  ] as const) {
    test(`shows the ${variant} refusal with ways forward that lead somewhere`, async ({ page, context }) => {
      await context.addCookies([{ name: "bp_mock_demo_start", value: variant, domain: "localhost", path: "/" }]);
      await page.goto("/demo");
      await expect(page.getByRole("heading", { name: title })).toBeVisible();
      await expect(page.getByText(message, { exact: false })).toBeVisible();
      if (variant === "ip_limit") await expect(page).toHaveScreenshot("demo-limit.png");

      const forward = (name: string) => page.getByRole("main").getByRole("link", { name });
      await expect(forward("Sign up free")).toHaveAttribute("href", "/login");
      await expect(forward("Watch the recorded replay")).toHaveAttribute("href", "/#demo");
      await forward("Browse the matchday").click();
      await expect(page).toHaveURL(/\/matchday$/);
      await expect(page.getByRole("article").first()).toBeVisible();
      await expect(page.getByRole("dialog")).toHaveCount(0);
    });
  }

  test("tells a regular signed-in user what a demo is", async ({ page, context }) => {
    await context.addCookies([{ name: "bp_mock_plan", value: "free", domain: "localhost", path: "/" }]);
    await page.goto("/demo");
    await expect(page.getByRole("heading", { name: "You're already signed in" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to the matchday" })).toBeVisible();
  });
});
