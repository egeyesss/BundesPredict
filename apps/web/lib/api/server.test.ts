import { http, HttpResponse } from "msw/http";
import { afterEach, describe, expect, it, vi } from "vitest";

import { loadFixtures } from "./server";
import { server } from "./mocks/node";
import { setupApiMocks } from "./mocks/vitest";

setupApiMocks();

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("loadFixtures", () => {
  it("returns the matchday's fixtures from the API", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.test");
    const outcome = await loadFixtures("next_matchday");
    expect(outcome.status).toBe("ok");
    if (outcome.status !== "ok") return;
    expect(outcome.fixtures).toHaveLength(9);
    expect(outcome.fixtures[0].home.code).toBe("SGE");
  });

  it("asks for the requested scope and sends the proxy secret", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.test");
    vi.stubEnv("PROXY_SECRET", "s3cret");
    let seen: { scope: string | null; secret: string | null } | null = null;
    server.use(
      http.get("*/api/v1/fixtures", ({ request }) => {
        seen = {
          scope: new URL(request.url).searchParams.get("scope"),
          secret: request.headers.get("x-proxy-secret"),
        };
        return HttpResponse.json([]);
      }),
    );
    await loadFixtures("week");
    expect(seen).toEqual({ scope: "week", secret: "s3cret" });
  });

  it("returns an empty list when the league has no matches", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.test");
    server.use(http.get("*/api/v1/fixtures", () => HttpResponse.json([])));
    expect(await loadFixtures("next_matchday")).toEqual({ status: "ok", fixtures: [] });
  });

  it("reports an error for a non-2xx answer", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.test");
    server.use(
      http.get("*/api/v1/fixtures", () =>
        HttpResponse.json({ code: "model_unavailable", message: "No fitted model." }, { status: 503 }),
      ),
    );
    expect(await loadFixtures("next_matchday")).toEqual({ status: "error" });
  });

  it("reports an error when the API cannot be reached", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.test");
    server.use(http.get("*/api/v1/fixtures", () => HttpResponse.error()));
    expect(await loadFixtures("next_matchday")).toEqual({ status: "error" });
  });
});
