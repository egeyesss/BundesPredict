import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxy, config } from "@/proxy";

import { buildUpstreamHeaders, upstreamUrl } from "./proxy";

describe("buildUpstreamHeaders", () => {
  const incoming = new Headers({
    host: "bundespredict.egeyesilyurt.ca",
    "x-forwarded-proto": "https",
    "x-forwarded-for": "203.0.113.7, 10.0.0.1",
    cookie: "sessionid=abc; csrftoken=def",
    "x-csrftoken": "def",
    "content-type": "application/json",
  });

  it("adds the secret, the caller address and the public host and scheme", () => {
    const headers = buildUpstreamHeaders(incoming, "s3cret");

    expect(headers.get("x-proxy-secret")).toBe("s3cret");
    expect(headers.get("x-client-ip")).toBe("203.0.113.7");
    expect(headers.get("x-forwarded-host")).toBe("bundespredict.egeyesilyurt.ca");
    expect(headers.get("x-forwarded-proto")).toBe("https");
  });

  it("passes cookies and the CSRF header through untouched", () => {
    const headers = buildUpstreamHeaders(incoming, "s3cret");

    expect(headers.get("cookie")).toBe("sessionid=abc; csrftoken=def");
    expect(headers.get("x-csrftoken")).toBe("def");
    expect(headers.get("content-type")).toBe("application/json");
  });

  it("overwrites anything the browser tried to supply for the injected headers", () => {
    const spoofed = new Headers(incoming);
    spoofed.set("x-proxy-secret", "guess");
    spoofed.set("x-client-ip", "1.2.3.4");
    spoofed.set("x-forwarded-host", "evil.example.com");

    const headers = buildUpstreamHeaders(spoofed, "s3cret");

    expect(headers.get("x-proxy-secret")).toBe("s3cret");
    expect(headers.get("x-client-ip")).toBe("203.0.113.7");
    expect(headers.get("x-forwarded-host")).toBe("bundespredict.egeyesilyurt.ca");
  });

  it("falls back to x-real-ip, then to unknown, when there is no forwarded chain", () => {
    const real = buildUpstreamHeaders(new Headers({ host: "h", "x-real-ip": " 198.51.100.2 " }), "s");
    const none = buildUpstreamHeaders(new Headers({ host: "h" }), "s");

    expect(real.get("x-client-ip")).toBe("198.51.100.2");
    expect(none.get("x-client-ip")).toBe("unknown");
  });

  it("sends an empty secret when none is configured so the backend rejects the call", () => {
    expect(buildUpstreamHeaders(incoming, "").get("x-proxy-secret")).toBe("");
  });

  it("defaults the scheme to http when the platform did not send one", () => {
    expect(buildUpstreamHeaders(new Headers({ host: "localhost:3000" }), "s").get("x-forwarded-proto")).toBe("http");
  });
});

describe("upstreamUrl", () => {
  it("keeps the path and the query string and swaps the origin", () => {
    const url = upstreamUrl(new URL("https://bundespredict.egeyesilyurt.ca/api/v1/fixtures?scope=week"), "https://api.example.com");

    expect(url.toString()).toBe("https://api.example.com/api/v1/fixtures?scope=week");
  });

  it("ignores a trailing slash on the base URL", () => {
    expect(upstreamUrl(new URL("http://x/accounts/google/login/"), "https://api.example.com/").toString()).toBe(
      "https://api.example.com/accounts/google/login/",
    );
  });
});

describe("proxy", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("rewrites to the backend and hands the injected headers to the destination", () => {
    vi.stubEnv("API_BASE_URL", "https://api.example.com");
    vi.stubEnv("PROXY_SECRET", "s3cret");
    const request = new NextRequest("https://bundespredict.egeyesilyurt.ca/_allauth/browser/v1/config", {
      headers: { host: "bundespredict.egeyesilyurt.ca", "x-forwarded-for": "203.0.113.7" },
    });

    const response = proxy(request);

    expect(response.headers.get("x-middleware-rewrite")).toBe("https://api.example.com/_allauth/browser/v1/config");
    expect(response.headers.get("x-middleware-request-x-proxy-secret")).toBe("s3cret");
    expect(response.headers.get("x-middleware-request-x-client-ip")).toBe("203.0.113.7");
  });

  it("only matches the backend's path prefixes", () => {
    expect(config.matcher).toEqual(["/api/:path*", "/_allauth/:path*", "/accounts/:path*"]);
  });
});
