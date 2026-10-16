import { describe, expect, it } from "vitest";

import { createApiClient } from "../client";
import { startPredictStream } from "../predict-stream";
import { server } from "./node";
import { scenarioForQuery } from "./handlers";
import { setupApiMocks } from "./vitest";
import { meFor } from "./data";
import { http, HttpResponse } from "msw/http";

setupApiMocks();

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

    expect((await client.GET("/api/v1/admin/metrics")).data?.active_subscribers).toBeGreaterThan(0);

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
