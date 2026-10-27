import { MOCK_PLAN_COOKIE } from "@/lib/auth/session-cookie";

import { readCookie } from "../client";
import type { Me } from "../types";
import { meFor } from "./data";
import { mockDemoUsage, mockUsage } from "./state";

export { MOCK_PLAN_COOKIE };
export const MOCK_CSRF_TOKEN = "mock-csrf-token";
export const MOCK_DEMO_EXPIRES_COOKIE = "bp_mock_demo_expires";
/** Set to `ip_limit` or `budget` to make `POST /demo/start` answer 429 with that code. */
export const MOCK_DEMO_START_COOKIE = "bp_mock_demo_start";

export type MockPlan = "free" | "pro" | "cancelling" | "pastdue" | "demo" | "nameless" | "admin";

const MOCK_PLANS: readonly MockPlan[] = ["free", "pro", "cancelling", "pastdue", "demo", "nameless", "admin"];

/** A mock cookie from the request, or from `document.cookie` for Node-side fetches under jsdom. */
export function mockCookie(cookies: Record<string, string>, name: string): string | null {
  return cookies[name] ?? (typeof document === "undefined" ? null : readCookie(document.cookie, name));
}

/**
 * Which mock account a request belongs to; no cookie means signed out. The request's own cookies
 * win (that is all the Next server pass has); `document.cookie` covers Node-side fetches under jsdom.
 */
export function mockPlanFrom(cookies: Record<string, string>): MockPlan | null {
  const fromDocument = typeof document === "undefined" ? null : readCookie(document.cookie, MOCK_PLAN_COOKIE);
  const value = cookies[MOCK_PLAN_COOKIE] ?? fromDocument;
  return MOCK_PLANS.find((plan) => plan === value) ?? null;
}

/** Browser only: the mock "session" is a cookie, so the server pass sees it on the next navigation. */
export function setMockSession(plan: MockPlan): void {
  if (typeof document !== "undefined") document.cookie = `${MOCK_PLAN_COOKIE}=${plan}; path=/; SameSite=Lax`;
}

export function clearMockSession(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${MOCK_PLAN_COOKIE}=; path=/; max-age=0`;
  document.cookie = `${MOCK_DEMO_EXPIRES_COOKIE}=; path=/; max-age=0`;
}

/** Remembers when the started demo expires, so a reload (which restarts the mock worker) keeps the same countdown. */
export function setMockDemoExpiry(iso: string): void {
  if (typeof document !== "undefined") document.cookie = `${MOCK_DEMO_EXPIRES_COOKIE}=${iso}; path=/; SameSite=Lax`;
}

export function setMockCsrfCookie(): void {
  if (typeof document !== "undefined") document.cookie = `csrftoken=${MOCK_CSRF_TOKEN}; path=/; SameSite=Lax`;
}

const PRO_RENEWS_AT = "2026-11-02T14:05:00Z";

export function meForMockPlan(plan: MockPlan, cookies: Record<string, string> = {}): Me {
  const pro = meFor("pro");
  switch (plan) {
    case "free":
      return { ...meFor("free"), usage: mockUsage.current() };
    case "pro":
      return pro;
    case "cancelling":
      return { ...pro, subscription: { status: "active", current_period_end: PRO_RENEWS_AT, cancel_at_period_end: true } };
    case "pastdue":
      return { ...pro, subscription: { status: "past_due", current_period_end: PRO_RENEWS_AT, cancel_at_period_end: false } };
    case "demo": {
      const fromCookie = mockCookie(cookies, MOCK_DEMO_EXPIRES_COOKIE);
      const expiry = fromCookie && !Number.isNaN(Date.parse(fromCookie)) ? { demo_expires_at: fromCookie } : {};
      return { ...meFor("demo"), ...expiry, usage: mockDemoUsage.current() };
    }
    case "admin":
      return { ...pro, name: "Ege", role: "admin" };
    case "nameless":
      return { ...meFor("free"), name: null, email: "a.very.long.email.address.for.layout.testing@subdomain.example-company.com" };
  }
}

/** PATCH /me edits, kept for the page's lifetime so a toggle sticks without a database. */
export const meChanges: { email_opt_in?: boolean; timezone?: string | null } = {};

export function resetMeChanges(): void {
  for (const key of Object.keys(meChanges)) delete meChanges[key as keyof typeof meChanges];
}
