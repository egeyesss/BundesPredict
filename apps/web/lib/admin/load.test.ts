import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const cookieHeader = vi.hoisted(() => ({ value: "" }));
vi.mock("next/headers", () => ({ cookies: async () => ({ toString: () => cookieHeader.value }) }));

import { loadAdminMetrics, parseRange } from "./load";

setupApiMocks();

beforeEach(() => {
  cookieHeader.value = "sessionid=abc";
  vi.stubEnv("API_BASE_URL", "http://api.mock.test");
  vi.stubEnv("PROXY_SECRET", "s3cret");
});

describe("loadAdminMetrics", () => {
  it("forwards the cookie and the range and returns the metrics", async () => {
    let seen: Request | null = null;
    server.use(
      http.get("*/api/v1/admin/metrics", ({ request }) => {
        seen = request;
        return HttpResponse.json({ masked: false, chats_per_day: [] });
      }),
    );

    const outcome = await loadAdminMetrics(7);

    expect(outcome.status).toBe("ok");
    expect(new URL(seen!.url).searchParams.get("days")).toBe("7");
    expect(seen!.headers.get("cookie")).toBe("sessionid=abc");
    expect(seen!.headers.get("x-proxy-secret")).toBe("s3cret");
  });

  it.each([
    [401, "signed_out"],
    [403, "forbidden"],
    [500, "error"],
  ])("maps a %i to %s", async (status, expected) => {
    server.use(http.get("*/api/v1/admin/metrics", () => HttpResponse.json({}, { status })));

    expect((await loadAdminMetrics(30)).status).toBe(expected);
  });

  it("treats a network failure as an error, not as signed out", async () => {
    server.use(http.get("*/api/v1/admin/metrics", () => HttpResponse.error()));

    expect((await loadAdminMetrics(30)).status).toBe("error");
  });
});

describe("parseRange", () => {
  it("accepts 7, 30 and 90 and falls back to 30", () => {
    expect(["7", "90", "30", "5", undefined, ["7", "30"]].map(parseRange)).toEqual([7, 90, 30, 30, 30, 30]);
  });
});
