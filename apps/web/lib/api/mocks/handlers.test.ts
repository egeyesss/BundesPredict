import { beforeEach, describe, expect, it } from "vitest";

import { createApiClient } from "../client";
import { startPredictStream } from "../predict-stream";
import { server } from "./node";
import { scenarioForQuery } from "./handlers";
import { clearMockSession, setMockSession } from "./session";
import { setupApiMocks } from "./vitest";
import { meFor } from "./data";
import { http, HttpResponse } from "msw/http";

setupApiMocks();

beforeEach(() => setMockSession("free"));

const BASE_URL = "http://api.test";
const client = createApiClient({ baseUrl: BASE_URL });

describe("read endpoints", () => {
  it("answers health", async () => {
    const { data } = await client.GET("/api/v1/health");
    expect(data).toEqual({ status: "ok", model_run_id: 57, db: "ok" });
  });

  it("lists the 18 clubs with codes and crest paths", async () => {
    const { data } = await client.GET("/api/v1/teams");
    expect(data).toHaveLength(18);
    expect(data?.find((t) => t.code === "BVB")).toMatchObject({
      name: "Borussia Dortmund",
      crest: "/crests/BVB.svg",
    });
  });

  it("lists the matchday's fixtures and one fixture's full markets", async () => {
    const list = await client.GET("/api/v1/fixtures", { params: { query: { scope: "week" } } });
    expect(list.data).toHaveLength(9);

    const detail = await client.GET("/api/v1/fixtures/{id}", { params: { path: { id: 803 } } });
    expect(detail.data?.markets.score_grid).toHaveLength(11);
    expect(detail.data?.home.code).toBe("BVB");
  });

  it("answers 404 with the error body for an unknown fixture", async () => {
    const { error, response } = await client.GET("/api/v1/fixtures/{id}", {
      params: { path: { id: 1 } },
    });
    expect(response.status).toBe(404);
    expect(error?.code).toBe("not_found");
  });

  it("answers /me for the free plan by default and PATCH echoes the changes", async () => {
    const me = await client.GET("/api/v1/me");
    expect(me.data).toMatchObject({ plan: "free", usage: { used: 1, limit: 3 } });

    const patched = await client.PATCH("/api/v1/me", {
      body: { email_opt_in: true, timezone: "America/Toronto" },
    });
    expect(patched.data).toMatchObject({ email_opt_in: true, timezone: "America/Toronto" });
  });

  it("answers /me with 401 until a mock session cookie exists", async () => {
    clearMockSession();
    const { error, response } = await client.GET("/api/v1/me");
    expect(response.status).toBe(401);
    expect(error?.code).toBe("not_authenticated");
  });

  it.each([
    ["pro", { plan: "pro", cancel: false, status: "active" }],
    ["cancelling", { plan: "pro", cancel: true, status: "active" }],
    ["pastdue", { plan: "pro", cancel: false, status: "past_due" }],
  ] as const)("serves the %s mock account", async (name, expected) => {
    setMockSession(name);
    const { data } = await client.GET("/api/v1/me");
    expect(data?.plan).toBe(expected.plan);
    expect(data?.subscription).toMatchObject({ status: expected.status, cancel_at_period_end: expected.cancel });
  });

  it("lets a test sign in as another plan", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json(meFor("pro"))));
    const { data } = await client.GET("/api/v1/me");
    expect(data?.plan).toBe("pro");
    expect(data?.subscription?.status).toBe("active");
  });

  it("serves conversations, one conversation with a prediction, and delete", async () => {
    const page = await client.GET("/api/v1/conversations");
    expect(page.data?.results.length).toBeGreaterThan(1);
    expect(page.data?.next).toBeNull();

    const id = page.data?.results[0].id ?? "";
    const detail = await client.GET("/api/v1/conversations/{id}", { params: { path: { id } } });
    const assistant = detail.data?.messages.find((m) => m.role === "assistant");
    expect(assistant?.prediction?.adjusted).not.toBeNull();

    const removed = await client.DELETE("/api/v1/conversations/{id}", { params: { path: { id } } });
    expect(removed.response.status).toBe(204);
  });

  it("serves billing redirects, track record, admin metrics, demo start and unsubscribe", async () => {
    expect((await client.POST("/api/v1/billing/checkout")).data?.url).toMatch(/^https:\/\//);
    expect((await client.POST("/api/v1/billing/portal")).data?.url).toMatch(/^https:\/\//);

    const record = (await client.GET("/api/v1/track-record")).data;
    expect(record?.live.kind).toBe("live");
    expect(record?.backtest.kind).toBe("backtest");
    expect(record?.calibration.length).toBeGreaterThan(5);

    setMockSession("admin");
    expect((await client.GET("/api/v1/admin/metrics")).data?.chats_per_day).toHaveLength(30);

    const demo = await client.POST("/api/v1/demo/start");
    expect(demo.response.status).toBe(201);
    expect(demo.data?.is_demo).toBe(true);

    const unsubscribe = await client.POST("/api/v1/email/unsubscribe", {
      body: { token: "signed" },
    });
    expect(unsubscribe.response.status).toBe(204);
  });
});

describe("unhandled requests", () => {
  it("fail the test instead of reaching the network", async () => {
    await expect(fetch(`${BASE_URL}/api/v1/not-in-the-contract`)).rejects.toThrow();
  });
});

describe("scenarioForQuery", () => {
  it.each([
    ["Dortmund v Hoffenheim without Guirassy", "happy"],
    ["Kane is doubtful for Bayern v Mainz", "tool_heavy"],
    ["trigger an error please", "error"],
    ["quota check", "quota_exceeded"],
    ["this is my last chat", "last_chat"],
    ["the model is unavailable", "model_unavailable"],
    ["rate limited", "rate_limited"],
    ["cut off mid answer", "cut_off"],
  ])("%s -> %s", (query, scenario) => {
    expect(scenarioForQuery(query)).toBe(scenario);
  });
});

describe("predict stream", () => {
  async function drain(query: string) {
    const started = await startPredictStream({ query }, { baseUrl: BASE_URL });
    if (!started.ok) return started;
    const events = [];
    for await (const event of started.events) events.push(event);
    return { ok: true as const, events };
  }

  it("streams the happy path to a result", async () => {
    const outcome = await drain("Guirassy is out, Dortmund v Hoffenheim");
    if (!outcome.ok) throw new Error("expected a stream");
    expect(outcome.events.at(-1)?.event).toBe("result");
  });

  it("streams the tool-heavy path with seven tool calls", async () => {
    const outcome = await drain("Kane is doubtful for Bayern v Mainz");
    if (!outcome.ok) throw new Error("expected a stream");
    const calls = outcome.events.filter((e) => e.event === "stage" && e.data.type === "tool_call");
    expect(calls).toHaveLength(7);
  });

  it("ends the error scenario with an error event", async () => {
    const outcome = await drain("please error out");
    if (!outcome.ok) throw new Error("expected a stream");
    expect(outcome.events.at(-1)).toMatchObject({ event: "error", data: { code: "agent_failed" } });
  });

  it("answers 402 with usage and an upgrade url before any stream starts", async () => {
    const outcome = await drain("quota please");
    expect(outcome).toMatchObject({
      ok: false,
      status: 402,
      error: { code: "quota_exceeded", usage: { used: 3, limit: 3 }, upgrade_url: "/account" },
    });
  });

  it("rejects an empty query with a validation error", async () => {
    const outcome = await drain("");
    expect(outcome).toMatchObject({ ok: false, status: 400, error: { code: "validation_error" } });
  });
});

describe("mock chat quota", () => {
  async function drain(query: string) {
    const started = await startPredictStream({ query }, { baseUrl: BASE_URL });
    if (!started.ok) return started;
    const events = [];
    for await (const event of started.events) events.push(event);
    return { ok: true as const, events };
  }

  it("counts each streamed chat against the free plan and reports it in /me and the quota event", async () => {
    const first = await drain("Guirassy is out");
    if (!first.ok) throw new Error("expected a stream");
    expect(first.events.find((e) => e.event === "quota")?.data).toMatchObject({ used: 2, limit: 3 });
    expect((await client.GET("/api/v1/me")).data?.usage.used).toBe(2);

    const second = await drain("Guirassy is out again");
    if (!second.ok) throw new Error("expected a stream");
    expect(second.events.find((e) => e.event === "quota")?.data).toMatchObject({ used: 3, limit: 3 });

    expect(await drain("one more")).toMatchObject({ ok: false, status: 402 });
  });

  it("does not count a chat that failed before the stream started", async () => {
    await drain("the model is unavailable");
    expect((await client.GET("/api/v1/me")).data?.usage.used).toBe(1);
  });

  it("starts every test with the first chat already used", async () => {
    expect((await client.GET("/api/v1/me")).data?.usage.used).toBe(1);
  });
});

describe("mock failure scenarios", () => {
  it("answers 503 model_unavailable before the stream", async () => {
    const started = await startPredictStream({ query: "the model is unavailable" }, { baseUrl: BASE_URL });
    expect(started).toMatchObject({ ok: false, status: 503, error: { code: "model_unavailable" } });
  });

  it("answers 429 with a Retry-After the client passes on", async () => {
    const started = await startPredictStream({ query: "rate limited" }, { baseUrl: BASE_URL });
    expect(started).toMatchObject({ ok: false, status: 429, error: { code: "rate_limited" }, retryAfterSeconds: 3 });
  });

  it("ends a cut-off stream after the stages with neither result nor error", async () => {
    const started = await startPredictStream({ query: "cut off mid answer" }, { baseUrl: BASE_URL });
    if (!started.ok) throw new Error("expected a stream");
    const names = [];
    for await (const event of started.events) names.push(event.event);
    expect(names).toContain("stage");
    expect(names).not.toContain("result");
    expect(names).not.toContain("error");
  });
});

describe("demo start", () => {
  const demoStart = () => client.POST("/api/v1/demo/start");

  it("signs the mock browser in as a fresh demo user who expires in 24 hours", async () => {
    clearMockSession();
    const before = Date.now();
    const started = await demoStart();
    expect(started.response.status).toBe(201);
    expect(started.data).toMatchObject({ plan: "demo", is_demo: true, usage: { used: 0, limit: 10 } });
    const expiresAt = Date.parse(started.data?.demo_expires_at ?? "");
    expect(expiresAt - before).toBeGreaterThan(24 * 3600e3 - 5000);
    expect(expiresAt - before).toBeLessThan(24 * 3600e3 + 5000);

    const me = await client.GET("/api/v1/me");
    expect(me.data).toMatchObject({ plan: "demo", is_demo: true, demo_expires_at: started.data?.demo_expires_at });
  });

  it.each([
    ["ip_limit", "demo_ip_limit"],
    ["budget", "demo_budget"],
  ])("answers 429 %s on request with its own code and a message", async (variant, code) => {
    clearMockSession();
    document.cookie = `bp_mock_demo_start=${variant}; path=/`;
    const { response, error } = await demoStart();
    document.cookie = "bp_mock_demo_start=; path=/; max-age=0";
    expect(response.status).toBe(429);
    expect(error?.code).toBe(code);
    expect(error?.message.length).toBeGreaterThan(10);
    expect((await client.GET("/api/v1/me")).response.status).toBe(401);
  });

  it("counts the demo user's chats against 10 in total, then answers 402", async () => {
    clearMockSession();
    await demoStart();
    for (let chat = 1; chat <= 10; chat++) {
      const start = await startPredictStream({ query: "Kane is out", conversation_id: null, fixture_id: null }, { baseUrl: BASE_URL });
      expect(start.ok).toBe(true);
      if (start.ok) for await (const event of start.events) if (event.event === "quota") expect(event.data).toMatchObject({ used: chat, limit: 10 });
    }
    const eleventh = await startPredictStream({ query: "again", conversation_id: null, fixture_id: null }, { baseUrl: BASE_URL });
    expect(eleventh).toMatchObject({ ok: false, status: 402 });
  });
});
