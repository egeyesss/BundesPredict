import { expect, test } from "@playwright/test";

// Google returns to the slash form of the callback. Next used to 308 it to the bare form and
// Django's APPEND_SLASH sent it straight back, so the sign-in looped until the browser gave up.
test("passes backend paths through with their trailing slash", async ({ request }) => {
  const response = await request.get("/accounts/google/login/callback/?state=x&code=y", { maxRedirects: 0 });

  expect(response.status()).not.toBe(308);
  expect(response.headers()["location"] ?? "").not.toMatch(/\/callback\?/);
});

/** Where a redirect points, as a path with its query, whether the server sent it relative or absolute. */
function redirectTarget(response: { headers(): Record<string, string> }): string {
  const target = new URL(response.headers()["location"], "http://localhost");
  return `${target.pathname}${target.search}`;
}

test.describe("pages that need a session", () => {
  test("answer a signed-out request with a 307 to the login page", async ({ request }) => {
    const response = await request.get("/account", { maxRedirects: 0 });

    expect(response.status()).toBe(307);
    expect(redirectTarget(response)).toBe("/login?next=%2Faccount");
  });

  test("keep the query string in the next path", async ({ request }) => {
    const response = await request.get("/account?checkout=success", { maxRedirects: 0 });

    expect(response.status()).toBe(307);
    expect(redirectTarget(response)).toBe("/login?next=%2Faccount%3Fcheckout%3Dsuccess");
  });

  test("send a signed-out chat visit to the login page too", async ({ request }) => {
    const response = await request.get("/chat?fixture=803", { maxRedirects: 0 });

    expect(response.status()).toBe(307);
    expect(redirectTarget(response)).toBe("/login?next=%2Fchat%3Ffixture%3D803");
  });

  test("render the page for a request that carries a session cookie", async ({ request }) => {
    const response = await request.get("/account", {
      maxRedirects: 0,
      headers: { cookie: "bp_mock_plan=free" },
    });

    expect(response.status()).toBe(200);
  });
});
