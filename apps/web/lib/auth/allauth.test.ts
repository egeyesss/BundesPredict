import { describe, expect, it } from "vitest";

import { clearMockSession } from "@/lib/api/mocks/session";
import { setupApiMocks } from "@/lib/api/mocks/vitest";
import { http, HttpResponse } from "msw/http";
import { server } from "@/lib/api/mocks/node";

import { confirmLoginCode, ensureCsrfCookie, requestLoginCode, signOut, signUp, verifyEmail } from "./allauth";

setupApiMocks();

describe("email code login", () => {
  it("requests a code for a known address and confirms it", async () => {
    clearMockSession();
    expect(await requestLoginCode("sam.rivera@example.com")).toEqual({ ok: true });
    expect(await confirmLoginCode("BCDFGHJK")).toEqual({ ok: true });
  });

  it("reports a wrong code as invalid", async () => {
    await requestLoginCode("sam.rivera@example.com");
    expect(await confirmLoginCode("ZZZZZZZZ")).toEqual({ ok: false, reason: "invalid_code" });
  });

  it("reports a missing or spent login flow as expired", async () => {
    clearMockSession();
    server.use(http.post("*/_allauth/browser/v1/auth/code/confirm", () => HttpResponse.json({ status: 401, data: { flows: [] } }, { status: 401 })));
    expect(await confirmLoginCode("BCDFGHJK")).toEqual({ ok: false, reason: "expired" });
  });

  it("rejects an invalid email", async () => {
    expect(await requestLoginCode("nope")).toEqual({ ok: false, reason: "invalid_email" });
  });

  it("surfaces rate limiting", async () => {
    expect(await requestLoginCode("limited@example.com")).toEqual({ ok: false, reason: "rate_limited" });
  });

  it("reports a network failure", async () => {
    server.use(http.post("*/_allauth/browser/v1/auth/code/request", () => HttpResponse.error()));
    expect(await requestLoginCode("sam.rivera@example.com")).toEqual({ ok: false, reason: "network" });
  });
});

describe("signup", () => {
  it("signs up with the email alone and verifies by code", async () => {
    expect(await signUp("new.person@example.com")).toEqual({ ok: true });
    expect(await verifyEmail("BCDFGHJK")).toEqual({ ok: true });
  });

  it("reports a wrong verification code", async () => {
    await signUp("new.person@example.com");
    expect(await verifyEmail("ZZZZZZZZ")).toEqual({ ok: false, reason: "invalid_code" });
  });
});

describe("CSRF and logout", () => {
  it("makes sure the csrftoken cookie exists by reading the session", async () => {
    expect(await ensureCsrfCookie()).toBeTruthy();
  });

  it("sends the CSRF header on writes", async () => {
    let header: string | null = null;
    await ensureCsrfCookie();
    server.use(
      http.post("*/_allauth/browser/v1/auth/code/request", ({ request }) => {
        header = request.headers.get("X-CSRFToken");
        return HttpResponse.json({ status: 401, data: { flows: [{ id: "login_by_code", is_pending: true }] } }, { status: 401 });
      }),
    );
    await requestLoginCode("sam.rivera@example.com");
    expect(header).toBeTruthy();
  });

  it("fetches a CSRF cookie itself when a write is sent before the page's own request returned", async () => {
    document.cookie = "csrftoken=; path=/; max-age=0";
    let header: string | null = null;
    server.use(
      http.post("*/_allauth/browser/v1/auth/code/request", ({ request }) => {
        header = request.headers.get("X-CSRFToken");
        return HttpResponse.json({ status: 401, data: { flows: [{ id: "login_by_code", is_pending: true }] } }, { status: 401 });
      }),
    );

    expect(await requestLoginCode("sam.rivera@example.com")).toEqual({ ok: true });
    expect(header).toBeTruthy();
  });

  it("signs out, treating allauth's 401 as success", async () => {
    expect(await signOut()).toEqual({ ok: true });
  });
});
