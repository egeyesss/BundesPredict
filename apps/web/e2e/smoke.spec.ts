import { expect, test } from "@playwright/test";

test("the chat page loads with its prompt input", async ({ page, context }) => {
  await context.addCookies([{ name: "bp_mock_plan", value: "free", domain: "localhost", path: "/" }]);
  await page.goto("/chat");
  await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
});
