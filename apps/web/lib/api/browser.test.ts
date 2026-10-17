import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it } from "vitest";

import { createCheckout, createPortal, fetchConversation, fetchConversations, fetchFixture, fetchMe, fetchWeekFixtures, updateMe } from "./browser";
import { notAuthenticated } from "./mocks/data";
import { server } from "./mocks/node";
import { setMockSession } from "./mocks/session";
import { setupApiMocks } from "./mocks/vitest";
import { ApiFailure } from "./use-resource";

setupApiMocks();

beforeEach(() => setMockSession("free"));

const signal = new AbortController().signal;

describe("browser api calls", () => {
  it("reads the signed-in user", async () => {
    expect(await fetchMe(signal)).toMatchObject({ plan: "free", usage: { used: 1, limit: 3 } });
  });

  it("reads one fixture with its markets", async () => {
    const fixture = await fetchFixture(803, signal);
    expect(fixture.home.short_name).toBe("Dortmund");
    expect(fixture.markets.score_grid).toHaveLength(11);
  });

  it("reads this week's fixtures and the conversation list", async () => {
    expect(await fetchWeekFixtures(signal)).toHaveLength(9);
    expect((await fetchConversations(signal)).results).toHaveLength(3);
  });

  it("reads one conversation with its messages", async () => {
    const conversation = await fetchConversation("7d2f0a3c-5b1e-4c8a-9a47-0e6f3b21c5d8", signal);
    expect(conversation.messages).toHaveLength(2);
  });

  it("throws an ApiFailure carrying the status and the server's code", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json(notAuthenticated, { status: 401 })));
    await expect(fetchMe(signal)).rejects.toMatchObject({ status: 401, code: "not_authenticated", message: "Sign in to continue." });
    await expect(fetchMe(signal)).rejects.toBeInstanceOf(ApiFailure);
  });

  it("throws not_found for an unknown fixture", async () => {
    await expect(fetchFixture(1, signal)).rejects.toMatchObject({ status: 404, code: "not_found" });
  });
});

describe("account writes", () => {
  it("patches the profile and returns the fresh account", async () => {
    const me = await updateMe({ email_opt_in: true, timezone: "Europe/Berlin", timezone_source: "manual" });
    expect(me).toMatchObject({ email_opt_in: true, timezone: "Europe/Berlin" });
  });

  it("starts checkout and the billing portal", async () => {
    expect(await createCheckout()).toMatch(/^https:\/\/checkout\.stripe\.com\//);
    expect(await createPortal()).toMatch(/^https:\/\/billing\.stripe\.com\//);
  });

  it("surfaces a missing billing account as its own code", async () => {
    server.use(
      http.post("*/api/v1/billing/portal", () =>
        HttpResponse.json({ code: "no_billing_account", message: "This account has no billing history yet." }, { status: 404 }),
      ),
    );
    await expect(createPortal()).rejects.toMatchObject({ status: 404, code: "no_billing_account" });
  });
});
