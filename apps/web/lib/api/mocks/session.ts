import { readCookie } from "../client";
import type { Me } from "../types";
import { meFor } from "./data";
import { mockUsage } from "./state";

export const MOCK_PLAN_COOKIE = "bp_mock_plan";
export const MOCK_CSRF_TOKEN = "mock-csrf-token";

export type MockPlan = "free" | "pro" | "cancelling" | "pastdue" | "demo";

const MOCK_PLANS: readonly MockPlan[] = ["free", "pro", "cancelling", "pastdue", "demo"];

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
  if (typeof document !== "undefined") document.cookie = `${MOCK_PLAN_COOKIE}=; path=/; max-age=0`;
}

export function setMockCsrfCookie(): void {
  if (typeof document !== "undefined") document.cookie = `csrftoken=${MOCK_CSRF_TOKEN}; path=/; SameSite=Lax`;
}

const PRO_RENEWS_AT = "2026-11-02T14:05:00Z";

export function meForMockPlan(plan: MockPlan): Me {
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
    case "demo":
      return meFor("demo");
  }
}

/** PATCH /me edits, kept for the page's lifetime so a toggle sticks without a database. */
export const meChanges: { email_opt_in?: boolean; timezone?: string | null } = {};

export function resetMeChanges(): void {
  for (const key of Object.keys(meChanges)) delete meChanges[key as keyof typeof meChanges];
}
