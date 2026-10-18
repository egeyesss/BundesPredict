import { expect, test, type Page } from "@playwright/test";

test.skip(({ viewport }) => (viewport?.width ?? 0) > 500, "phone layout only");
test.use({ reducedMotion: "reduce", timezoneId: "America/Toronto", locale: "en-US" });

async function signInAs(page: Page, plan: "free" | "nameless") {
  await page.context().addCookies([{ name: "bp_mock_plan", value: plan, domain: "localhost", path: "/" }]);
}

const horizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

/** Controls whose tap area, counting a stretched ::after, is under 44px in either direction. Inline links inside a sentence and the OTP slots are left out. */
const smallTapTargets = (page: Page) =>
  page.evaluate(() => {
    const controls = document.querySelectorAll<HTMLElement>("a[href], button, input:not([type=hidden]), select, textarea, summary, [role=switch]");
    const found: string[] = [];
    for (const element of controls) {
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (box.width === 0 || box.height === 0 || style.visibility === "hidden") continue;
      if (element.classList.contains("sr-only") || element.closest("[aria-hidden='true'], [data-otp-root]")) continue;
      if (element.matches("p a, p button")) continue;
      const stretched = getComputedStyle(element, "::after");
      const grows = stretched.position === "absolute" && stretched.content !== "none";
      const width = Math.max(box.width, grows ? parseFloat(stretched.width) : 0);
      const height = Math.max(box.height, grows ? parseFloat(stretched.height) : 0);
      if (width < 43.5 || height < 43.5) {
        found.push(`${element.tagName.toLowerCase()} "${(element.getAttribute("aria-label") ?? element.textContent ?? "").trim().slice(0, 30)}" ${Math.round(width)}x${Math.round(height)}`);
      }
    }
    return found;
  });

test.describe("phone layout at 375px", () => {
  test("matchday fits the screen and every control is a 44px target", async ({ page }) => {
    await signInAs(page, "free");
    await page.goto("/matchday");
    await expect(page.getByRole("article").first()).toBeVisible();

    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    expect(await smallTapTargets(page)).toEqual([]);
  });

  test("chat keeps its controls at 44px and the composer on one line", async ({ page }) => {
    await signInAs(page, "free");
    await page.goto("/chat?fixture=803");
    const composer = page.getByRole("textbox", { name: "Message" });
    await expect(composer).toBeVisible();

    expect(await smallTapTargets(page)).toEqual([]);
    expect((await composer.boundingBox())?.height).toBeLessThan(60);
  });

  test("a long email does not push the account page or the menu card off screen", async ({ page }) => {
    await signInAs(page, "nameless");
    await page.goto("/account");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    await page.getByRole("button", { name: "Open menu" }).click();
    const card = page.locator(".menu-who");
    await expect(card).toBeVisible();
    const cardBox = await card.boundingBox();
    const nameBox = await card.locator(".menu-who-name").boundingBox();
    expect(nameBox!.x + nameBox!.width).toBeLessThanOrEqual(cardBox!.x + cardBox!.width);
  });

  test("the sign-in page keeps its link buttons at 44px", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Email me a sign-in code" })).toBeVisible();

    expect(await smallTapTargets(page)).toEqual([]);
  });
});
