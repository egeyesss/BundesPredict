import { expect, test } from "@playwright/test";

test("the chat page loads with its prompt input", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("textbox")).toBeVisible();
});
