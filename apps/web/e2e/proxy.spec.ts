import { expect, test } from "@playwright/test";

// Google returns to the slash form of the callback. Next used to 308 it to the bare form and
// Django's APPEND_SLASH sent it straight back, so the sign-in looped until the browser gave up.
test("passes backend paths through with their trailing slash", async ({ request }) => {
  const response = await request.get("/accounts/google/login/callback/?state=x&code=y", { maxRedirects: 0 });

  expect(response.status()).not.toBe(308);
  expect(response.headers()["location"] ?? "").not.toMatch(/\/callback\?/);
});
