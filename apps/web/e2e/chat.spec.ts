import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.use({ timezoneId: "America/Toronto", locale: "en-US" });

// The mock conversations are dated 2026-10-15; fixing the clock keeps their Today and This week groups stable.
test.beforeEach(async ({ page, context }) => {
  await context.addCookies([{ name: "bp_mock_plan", value: "free", domain: "localhost", path: "/" }]);
  await page.clock.setFixedTime(new Date("2026-10-16T15:00:00Z"));
});

const message = (page: Page) => page.getByRole("textbox", { name: "Message" });
const send = (page: Page) => page.getByRole("button", { name: "Send" });
const pinned = (page: Page) => page.getByRole("region", { name: "Pinned fixture" });
const result = (page: Page) => page.getByRole("region", { name: "Updated odds" });

async function openDortmund(page: Page) {
  await page.goto("/chat?fixture=803");
  await expect(pinned(page)).toContainText("Hoffenheim");
  await expect(message(page)).toBeEnabled();
}

async function ask(page: Page, text: string) {
  await message(page).fill(text);
  await send(page).click();
}

test.describe("a full chat", () => {
  test.use({ reducedMotion: "no-preference" });

  test("walks the orb through its states and moves the bars from baseline to adjusted", async ({ page }) => {
    await openDortmund(page);
    await expect(page.getByRole("main").getByText("2 of 3 free chats left today")).toBeVisible();
    await expect(pinned(page).getByText("Model", { exact: true })).toBeVisible();

    await page.evaluate(() => {
      const seen: string[] = [];
      Object.assign(window, { __orbStates: seen });
      new MutationObserver(() => {
        const orb = document.querySelector('[role="log"] [data-orb]');
        const state = orb?.getAttribute("data-orb-state");
        if (state && seen.at(-1) !== state) seen.push(state);
      }).observe(document.body, { subtree: true, attributes: true, childList: true, attributeFilter: ["data-orb-state"] });
    });

    await ask(page, "Guirassy is out for Dortmund, how does that change it?");
    await expect(page.getByRole("log").getByText("Guirassy is out for Dortmund, how does that change it?")).toBeVisible();

    await expect(result(page)).toBeVisible();
    await expect(result(page).getByText("Model only").first()).toBeVisible();
    await expect(result(page).getByText("With your news").first()).toBeVisible();
    await expect(result(page).getByTestId("delta")).toHaveCount(3);
    await expect(result(page).getByText(/player_out/)).toBeVisible();

    const states = await page.evaluate(() => (window as unknown as { __orbStates: string[] }).__orbStates);
    expect(states.slice(0, 4)).toEqual(["thinking", "tool", "thinking", "tool"]);
    expect(states).toContain("done");

    await expect(page.getByRole("main").getByText("1 of 3 free chats left today")).toBeVisible();
    await expect(pinned(page).getByText("With your news")).toBeVisible();
  });

  test("collapses the agent steps once the explanation starts and toggles the original odds", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "Guirassy is out for Dortmund");
    await expect(result(page)).toBeVisible();

    const steps = page.getByRole("log").locator("details").first();
    await expect(steps).not.toHaveAttribute("open", "");
    await expect(steps.locator("summary")).toContainText("3 agent steps");

    await pinned(page).getByRole("button", { name: "Show original odds" }).click();
    await expect(pinned(page).getByText("Original model")).toBeVisible();
    await pinned(page).getByRole("button", { name: "Show odds with your news" }).click();
    await expect(pinned(page).getByText("With your news")).toBeVisible();
  });

  test("opens More markets with the scoreline heatmap", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "Guirassy is out for Dortmund");
    const drawer = result(page).locator("details", { hasText: "More markets and scorelines" });
    await expect(drawer).toHaveAttribute("open", "");
    await expect(drawer.getByRole("img", { name: /Scoreline probabilities/ })).toBeVisible();
    await expect(drawer.getByText("Over 2.5 goals")).toBeVisible();
    await expect(drawer.getByText("Most likely scores")).toBeVisible();
    await drawer.getByRole("button", { name: "Model only" }).click();
    await expect(drawer.getByRole("button", { name: "Model only" })).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("shows the whole explanation at once", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "Guirassy is out for Dortmund");
    await expect(page.getByText(/The base model has Dortmund at 61%/)).toBeVisible();
    await expect(result(page)).toBeVisible();
    await expect(page.locator(".caret")).toHaveCount(0);
  });
});

test.describe("quota and failures", () => {
  test.use({ reducedMotion: "reduce" });

  test("over quota shows the upgrade prompt that links to the account page", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "quota please");
    const prompt = page.getByRole("status").filter({ hasText: "used today's 3 free chats" });
    await expect(prompt).toBeVisible();
    await expect(prompt.getByRole("link", { name: /Upgrade to Pro/ })).toHaveAttribute("href", "/account");
    await expect(message(page)).toHaveCount(0);
  });

  test("the last free chat leads to the prompt on the next send", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "last chat please");
    await expect(result(page)).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "used today's 3 free chats" })).toBeVisible();
  });

  test("a model outage says what broke and gives the chat back", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "unavailable");
    await expect(page.getByText("The model isn't available right now. This chat wasn't counted.")).toBeVisible();
    await expect(page.getByRole("main").getByText("2 of 3 free chats left today")).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("a mid-stream failure ends in the error state", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "this will fail");
    await expect(page.getByRole("log").getByText("The prediction could not be completed. Try again.")).toBeVisible();
    await message(page).fill("one more go");
    await expect(send(page)).toBeEnabled();
  });

  test("a rate limit counts down and re-enables Send", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "rate limited");
    const banner = page.getByRole("alert").filter({ hasText: "Too many messages at once" });
    await expect(banner).toContainText(/in \d+ s/);
    await expect(send(page)).toBeDisabled();
    await expect(page.getByText("You can send again.")).toBeVisible({ timeout: 10_000 });
    await message(page).fill("another try");
    await expect(send(page)).toBeEnabled();
  });

  test("a dropped connection marks the answer as cut off", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "cut off");
    await expect(page.getByText("The answer was cut off by a lost connection.")).toBeVisible();
  });
});

test.describe("history", () => {
  test.use({ reducedMotion: "reduce" });

  test("resumes a saved conversation from the sidebar", async ({ page, viewport }) => {
    test.skip((viewport?.width ?? 0) < 860, "the sidebar is a sheet on phones");
    await page.goto("/chat");
    const history = page.getByRole("complementary", { name: "Chat history" });
    await expect(history.getByRole("link")).toHaveCount(4);

    await history.getByRole("link", { name: /Guirassy is out for Dortmund/ }).click();
    await expect(page).toHaveURL(/\/chat\/7d2f0a3c-5b1e-4c8a-9a47-0e6f3b21c5d8$/);
    await expect(page.getByRole("log").getByText("Guirassy is out for Dortmund, how does that change Dortmund v Hoffenheim?")).toBeVisible();
    await expect(result(page)).toBeVisible();
    await expect(pinned(page)).toContainText("Hoffenheim");
  });

  test("the history sheet opens from the History button on a phone", async ({ page, viewport }) => {
    test.skip((viewport?.width ?? 0) >= 860, "phone layout only");
    await page.goto("/chat");
    await page.getByRole("button", { name: "History" }).click();
    const sheet = page.getByRole("dialog", { name: "Chat history" });
    await expect(sheet.getByRole("link", { name: /Guirassy is out for Dortmund/ })).toBeVisible();
    await sheet.getByRole("link", { name: /Guirassy is out for Dortmund/ }).click();
    await expect(page).toHaveURL(/\/chat\/7d2f0a3c/);
    await expect(sheet).toBeHidden();
  });

  test("a new chat with no fixture asks for one", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("link", { name: "Pick a fixture" })).toHaveAttribute("href", "/matchday");
    await expect(message(page)).toBeVisible();
  });
});

test.describe("chat accessibility and visuals", () => {
  test.use({ reducedMotion: "reduce" });

  test("has no axe violations with a finished result", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "Guirassy is out for Dortmund");
    await expect(result(page)).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test("matches the visual snapshot with a finished result", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "Guirassy is out for Dortmund");
    await expect(result(page)).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => [...document.images].every((image) => image.complete));
    await expect(page.locator("main")).toHaveScreenshot("chat-result.png");
  });

  test("matches the visual snapshot when over quota", async ({ page }) => {
    await openDortmund(page);
    await ask(page, "quota please");
    await expect(page.getByRole("status").filter({ hasText: "used today's 3 free chats" })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator("main")).toHaveScreenshot("chat-over-quota.png");
  });
});
