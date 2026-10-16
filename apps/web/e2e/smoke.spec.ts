import { expect, test } from "@playwright/test";

test("the chat page loads with its prompt input", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
});
