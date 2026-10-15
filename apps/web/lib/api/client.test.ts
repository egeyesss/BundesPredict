import { describe, expect, it, vi } from "vitest";

import { createApiClient, csrfMiddleware, readCookie } from "./client";

function jsonFetch(body: unknown, status = 200) {
  return vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
}

describe("readCookie", () => {
  it("finds a cookie among several", () => {
    expect(readCookie("a=1; csrftoken=abc123; b=2", "csrftoken")).toBe("abc123");
  });

  it("returns null when the cookie is missing", () => {
    expect(readCookie("a=1", "csrftoken")).toBeNull();
    expect(readCookie("", "csrftoken")).toBeNull();
  });

  it("decodes percent-encoded values and keeps equals signs", () => {
    expect(readCookie("token=a%20b=c", "token")).toBe("a b=c");
  });
});

describe("createApiClient", () => {
  it("calls typed paths and returns the parsed body", async () => {
    const fetch = jsonFetch([]);
    const client = createApiClient({ baseUrl: "http://api.test", fetch });

    const { data, error } = await client.GET("/api/v1/fixtures", {
      params: { query: { scope: "week" } },
    });

    expect(error).toBeUndefined();
    expect(data).toEqual([]);
    const request = fetch.mock.calls[0][0] as Request;
    expect(request.url).toBe("http://api.test/api/v1/fixtures?scope=week");
  });

  it("returns the contract error body on a failure status", async () => {
    const fetch = jsonFetch({ code: "model_unavailable", message: "No fitted model" }, 503);
    const client = createApiClient({ baseUrl: "http://api.test", fetch });

    const { data, error, response } = await client.GET("/api/v1/fixtures");

    expect(data).toBeUndefined();
    expect(response.status).toBe(503);
    expect(error).toEqual({ code: "model_unavailable", message: "No fitted model" });
  });

  it("sends configured headers such as the proxy secret", async () => {
    const fetch = jsonFetch([]);
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch,
      headers: { "x-proxy-secret": "s3cret" },
    });

    await client.GET("/api/v1/teams");

    expect((fetch.mock.calls[0][0] as Request).headers.get("x-proxy-secret")).toBe("s3cret");
  });
});

describe("csrfMiddleware", () => {
  const options = {} as never;
  const run = (method: string, cookies: string) => {
    const request = new Request("http://api.test/api/v1/me", { method });
    csrfMiddleware(() => cookies).onRequest?.({
      request,
      schemaPath: "/api/v1/me",
      params: {},
      id: "1",
      options,
    });
    return request;
  };

  it("copies the csrftoken cookie into X-CSRFToken on writes", () => {
    expect(run("PATCH", "csrftoken=tok").headers.get("X-CSRFToken")).toBe("tok");
    expect(run("POST", "csrftoken=tok").headers.get("X-CSRFToken")).toBe("tok");
    expect(run("DELETE", "csrftoken=tok").headers.get("X-CSRFToken")).toBe("tok");
  });

  it("leaves reads alone", () => {
    expect(run("GET", "csrftoken=tok").headers.has("X-CSRFToken")).toBe(false);
  });

  it("sends nothing when there is no cookie yet", () => {
    expect(run("POST", "other=1").headers.has("X-CSRFToken")).toBe(false);
  });
});
